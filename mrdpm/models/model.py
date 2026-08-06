import torch
import tqdm
import os
import copy
from core.base_model import BaseModel
from core.logger import LogTracker


class EMA:
    def __init__(self, beta=0.9999):
        super().__init__()
        self.beta = beta

    def update_model_average(self, ma_model, current_model):
        for current_params, ma_params in zip(
            current_model.parameters(), ma_model.parameters()
        ):
            old_weight, up_weight = ma_params.data, current_params.data
            ma_params.data = self.update_average(old_weight, up_weight)

    def update_average(self, old, new):
        if old is None:
            return new
        return old * self.beta + (1 - self.beta) * new


class Palette(BaseModel):
    def __init__(
        self,
        networks,
        losses,
        sample_num,
        task,
        optimizers,
        ema_scheduler=None,
        **kwargs,
    ):
        """必须使用kwargs初始化BaseModel"""

        # 首先从kwargs中提取预训练路径参数，避免传递给父类
        bran_pretrained_path = kwargs.pop("bran_pretrained_path", None)

        super(Palette, self).__init__(**kwargs)

        # 存储预训练路径
        self.bran_pretrained_path = bran_pretrained_path

        """网络、数据加载器、优化器、损失函数等"""
        self.loss_fn = losses[0]
        self.netG = networks[0]
        self.sample_num = sample_num
        self.task = task

        # 增强的预训练权重处理逻辑
        self._handle_pretrained_weights()

        if ema_scheduler is not None:
            self.ema_scheduler = ema_scheduler
            self.netG_EMA = copy.deepcopy(self.netG)
            self.EMA = EMA(beta=self.ema_scheduler["ema_decay"])
        else:
            self.ema_scheduler = None

        # 设备设置
        self.netG = self.set_device(self.netG, distributed=self.opt["distributed"])
        if self.ema_scheduler is not None:
            self.netG_EMA = self.set_device(
                self.netG_EMA, distributed=self.opt["distributed"]
            )

        # 加载网络权重
        self.load_networks()

        # 优化器设置
        self.optG = torch.optim.Adam(
            list(filter(lambda p: p.requires_grad, self.netG.parameters())),
            **optimizers[0],
        )
        self.optimizers.append(self.optG)

        # 学习率调度器
        lambda1 = lambda epoch: 1 if epoch < 100 else 1 - (epoch - 100) / (200 - 100)
        self.lr_scheduler = torch.optim.lr_scheduler.LambdaLR(
            self.optG, lr_lambda=lambda1
        )

        # 恢复训练状态
        self.resume_training()

        # 设置网络损失和噪声调度
        if self.opt["distributed"]:
            self.netG.module.set_loss(self.loss_fn)
            self.netG.module.set_new_noise_schedule(phase=self.phase)
        else:
            self.netG.set_loss(self.loss_fn)
            self.netG.set_new_noise_schedule(phase=self.phase)

        """可以在继承类中重写以记录更多信息"""
        self.train_metrics = LogTracker(*[m.__name__ for m in losses], phase="train")
        self.val_metrics = LogTracker(*[m.__name__ for m in self.metrics], phase="val")
        self.test_metrics = LogTracker(
            *[m.__name__ for m in self.metrics], phase="test"
        )

    def _handle_pretrained_weights(self):
        """处理预训练权重加载"""
        print(f"📋 预训练权重路径: {self.bran_pretrained_path}")

        if not self.bran_pretrained_path:
            print("⚠️ 未提供预训练权重路径")
            return

        if not os.path.exists(self.bran_pretrained_path):
            print(f"❌ 预训练权重文件不存在: {self.bran_pretrained_path}")
            return

        # 设置预训练路径
        if hasattr(self.netG, "set_pretrained_path"):
            try:
                self.netG.set_pretrained_path(self.bran_pretrained_path)
                print(f"✅ 成功设置预训练权重路径")

                # 验证权重加载
                if hasattr(self.netG, "verify_pretrained_weights"):
                    self.netG.verify_pretrained_weights()
            except Exception as e:
                print(f"❌ 设置预训练权重路径失败: {e}")
        else:
            print("⚠️ Network类没有set_pretrained_path方法")

    def set_input(self, data):
        """必须在张量中使用set_device"""
        self.cond_image = self.set_device(data.get("cond_image")).type(torch.float32)
        self.gt_image = self.set_device(data.get("gt_image")).type(torch.float32)
        self.mask = self.set_device(data.get("mask"))
        self.mask_image = data.get("mask_image")
        self.path = data["path"]
        self.batch_size = len(data["path"])

    def get_current_visuals(self, phase="train"):
        """获取当前可视化结果"""
        visuals = {
            "gt_image": self.gt_image.detach()[:].float().cpu(),
            "cond_image": self.cond_image.detach()[:].float().cpu(),
        }

        if self.task in ["my_mission_mask", "my_mission_mask_ddim"]:
            visuals.update(
                {
                    "mask": self.mask.detach()[:].float().cpu(),
                    "mask_image": self.mask_image,
                }
            )

        if phase != "train":
            visuals.update({"output": self.output.detach()[:].float().cpu()})

        return visuals

    def save_current_results(self):
        """保存当前结果"""
        ret_path = []
        ret_result = []

        for idx in range(self.batch_size):
            ret_path.append(f"GT_{self.path[idx]}")
            ret_result.append(self.gt_image[idx].detach().float().cpu())

            ret_path.append(f"Process_{self.path[idx]}")
            ret_result.append(
                self.visuals[idx :: self.batch_size].detach().float().cpu()
            )

            ret_path.append(f"Out_{self.path[idx]}")
            ret_result.append(self.output[idx].detach().float().cpu())

        if self.task in ["my_mission_mask", "my_mission_mask_ddim"]:
            ret_path.extend([f"Mask_{name}" for name in self.path])
            ret_result.extend(self.mask_image)

        self.results_dict = self.results_dict._replace(name=ret_path, result=ret_result)
        return self.results_dict._asdict()

    def train_step(self):
        """训练步骤"""
        self.netG.train()
        self.train_metrics.reset()

        for train_data in tqdm.tqdm(self.phase_loader, desc=f"训练 Epoch {self.epoch}"):
            self.set_input(train_data)
            self.optG.zero_grad()

            # 前向传播和损失计算
            loss = self.netG(self.gt_image, self.cond_image, mask=self.mask)
            loss.backward()
            self.optG.step()

            self.iter += self.batch_size
            self.writer.set_iter(self.epoch, self.iter, phase="train")
            self.train_metrics.update(self.loss_fn.__name__, loss.item())

            # 定期记录日志
            if self.iter % self.opt["train"]["log_iter"] == 0:
                for key, value in self.train_metrics.result().items():
                    self.logger.info("{:5s}: {:.6f}\t".format(str(key), value))
                    self.writer.add_scalar(key, value)

                for key, value in self.get_current_visuals().items():
                    self.writer.add_images(key, value)

            # EMA更新
            if self.ema_scheduler is not None:
                if (
                    self.iter > self.ema_scheduler["ema_start"]
                    and self.iter % self.ema_scheduler["ema_iter"] == 0
                ):
                    self.EMA.update_model_average(self.netG_EMA, self.netG)

        # 学习率调整
        self.lr_scheduler.step()
        current_lr = self.lr_scheduler.get_last_lr()
        self.logger.info(f"当前学习率: {current_lr}")

        return self.train_metrics.result()

    def val_step(self):
        """验证步骤"""
        self.netG.eval()
        self.val_metrics.reset()

        with torch.no_grad():
            for val_data in tqdm.tqdm(self.val_loader, desc="验证"):
                self.set_input(val_data)

                if self.opt["distributed"]:
                    if self.task in ["my_mission_mask"]:
                        self.output, self.visuals = self.netG.module.restoration(
                            self.cond_image,
                            y_t=self.cond_image,
                            y_0=self.gt_image,
                            mask=self.mask,
                            sample_num=self.sample_num,
                            target=self.gt_image,
                        )
                else:
                    if self.task in ["my_mission_mask"]:
                        self.output, self.visuals = self.netG.restoration(
                            self.cond_image,
                            y_t=self.cond_image,
                            y_0=self.gt_image,
                            mask=self.mask,
                            sample_num=self.sample_num,
                            target=self.gt_image,
                        )

                self.iter += self.batch_size
                self.writer.set_iter(self.epoch, self.iter, phase="val")

                # 计算指标
                for met in self.metrics:
                    key = met.__name__
                    value = met(self.gt_image, self.output)
                    self.val_metrics.update(key, value)
                    self.writer.add_scalar(key, value)

                # 记录可视化结果
                for key, value in self.get_current_visuals(phase="val").items():
                    self.writer.add_images(key, value)

                self.writer.save_images(self.save_current_results())

        return self.val_metrics.result()

    def test(self):
        """测试步骤"""
        self.netG.eval()
        self.test_metrics.reset()

        with torch.no_grad():
            for phase_data in tqdm.tqdm(self.phase_loader, desc="测试"):
                self.set_input(phase_data)

                if self.opt["distributed"]:
                    if self.task in ["my_mission_mask"]:
                        self.output, self.visuals = self.netG.module.restoration(
                            self.cond_image,
                            y_t=self.cond_image,
                            y_0=self.gt_image,
                            mask=self.mask,
                            sample_num=self.sample_num,
                            target=self.gt_image,
                        )
                else:
                    if self.task in ["my_mission_mask"]:
                        self.output, self.visuals = self.netG.restoration(
                            self.cond_image,
                            y_t=self.cond_image,
                            y_0=self.gt_image,
                            mask=self.mask,
                            sample_num=self.sample_num,
                            target=self.gt_image,
                        )

                self.iter += self.batch_size
                self.writer.set_iter(self.epoch, self.iter, phase="test")

                # 计算测试指标
                for met in self.metrics:
                    key = met.__name__
                    value = met(self.gt_image, self.output)
                    self.test_metrics.update(key, value)
                    self.writer.add_scalar(key, value)

                # 记录可视化结果
                for key, value in self.get_current_visuals(phase="test").items():
                    self.writer.add_images(key, value)

                self.writer.save_images(self.save_current_results())

        # 记录测试结果
        test_log = self.test_metrics.result()
        test_log.update({"epoch": self.epoch, "iters": self.iter})

        # 保存到文件
        with open("ddim_test.txt", "a") as file:
            file.write(f"{self.logger.opt['path']['resume_state']}   ")
            file.write(f"{test_log['test/mae'].cpu().numpy()}\n")

        # 打印结果
        for key, value in test_log.items():
            self.logger.info("{:5s}: {}\t".format(str(key), value))

    def load_networks(self):
        """加载网络权重"""
        if self.opt["distributed"]:
            netG_label = self.netG.module.__class__.__name__
        else:
            netG_label = self.netG.__class__.__name__

        self.load_network(network=self.netG, network_label=netG_label, strict=False)

        if self.ema_scheduler is not None:
            self.load_network(
                network=self.netG_EMA, network_label=netG_label + "_ema", strict=False
            )

    def save_everything(self):
        """保存所有内容"""
        if self.opt["distributed"]:
            netG_label = self.netG.module.__class__.__name__
        else:
            netG_label = self.netG.__class__.__name__

        self.save_network(network=self.netG, network_label=netG_label)

        if self.ema_scheduler is not None:
            self.save_network(network=self.netG_EMA, network_label=netG_label + "_ema")

        self.save_training_state()
