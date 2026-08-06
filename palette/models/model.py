import torch
import tqdm
from core.base_model import BaseModel
from core.logger import LogTracker
import copy


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
        """must to init BaseModel with kwargs"""
        super(Palette, self).__init__(**kwargs)

        """ networks, dataloder, optimizers, losses, etc. """
        self.loss_fn = losses[0]
        self.netG = networks[0]
        if ema_scheduler is not None:
            self.ema_scheduler = ema_scheduler
            self.netG_EMA = copy.deepcopy(self.netG)
            self.EMA = EMA(beta=self.ema_scheduler["ema_decay"])
        else:
            self.ema_scheduler = None

        """ networks can be a list, and must convert by self.set_device function if using multiple GPU. """
        self.netG = self.set_device(self.netG, distributed=self.opt["distributed"])
        if self.ema_scheduler is not None:
            self.netG_EMA = self.set_device(
                self.netG_EMA, distributed=self.opt["distributed"]
            )
        self.load_networks()

        self.optG = torch.optim.Adam(
            list(filter(lambda p: p.requires_grad, self.netG.parameters())),
            **optimizers[0],
        )

        self.optimizers.append(self.optG)
        lambda1 = lambda epoch: 1 if epoch < 100 else 1 - (epoch - 100) / (200 - 100)
        self.lr_scheduler = torch.optim.lr_scheduler.LambdaLR(
            self.optG, lr_lambda=lambda1
        )
        # self.lr_scheduler = torch.optim.lr_scheduler.LinearLR(self.optG,start_factor=1,end_factor=0.5,total_iters=self.opt['train']['n_epoch'],last_epoch=-1)  # 用于控制学习率的变化，临时使用
        self.resume_training()

        if self.opt["distributed"]:
            self.netG.module.set_loss(self.loss_fn)
            self.netG.module.set_new_noise_schedule(phase=self.phase)
        else:
            self.netG.set_loss(self.loss_fn)
            self.netG.set_new_noise_schedule(phase=self.phase)

        """ can rewrite in inherited class for more informations logging """
        self.train_metrics = LogTracker(*[m.__name__ for m in losses], phase="train")
        self.val_metrics = LogTracker(*[m.__name__ for m in self.metrics], phase="val")
        self.test_metrics = LogTracker(
            *[m.__name__ for m in self.metrics], phase="test"
        )

        self.sample_num = sample_num
        self.task = task

    def set_input(self, data):
        """must use set_device in tensor"""
        self.cond_image = self.set_device(data.get("cond_image")).type(torch.float32)
        self.gt_image = self.set_device(data.get("gt_image")).type(torch.float32)
        self.mask = self.set_device(data.get("mask"))
        self.mask_image = data.get("mask_image")
        self.path = data["path"]
        self.batch_size = len(data["path"])

    def get_current_visuals(self, phase="train"):
        dict = {
            # 'gt_image': (self.gt_image.detach()[:].float().cpu()+1)/2,
            # 'cond_image': (self.cond_image.detach()[:].float().cpu()+1)/2,
            "gt_image": self.gt_image.detach()[:].float().cpu(),
            "cond_image": self.cond_image.detach()[:].float().cpu(),
        }
        if self.task in [
            "inpainting",
            "uncropping",
            "my_mission_mask",
            "my_mission_mask_ddim",
        ]:
            dict.update(
                {
                    "mask": self.mask.detach()[:].float().cpu(),
                    # 'mask_image': (self.mask_image+1)/2,
                    "mask_image": self.mask_image,
                }
            )
        if phase != "train":
            dict.update(
                {
                    # 'output': (self.output.detach()[:].float().cpu()+1)/2
                    "output": self.output.detach()[:].float().cpu()
                }
            )
        return dict

    def save_current_results(self):
        ret_path = []
        ret_result = []
        for idx in range(self.batch_size):
            ret_path.append("GT_{}".format(self.path[idx]))
            ret_result.append(self.gt_image[idx].detach().float().cpu())

            ret_path.append("Process_{}".format(self.path[idx]))
            ret_result.append(
                self.visuals[idx :: self.batch_size].detach().float().cpu()
            )

            ret_path.append("Out_{}".format(self.path[idx]))
            # ret_result.append(self.visuals[idx-self.batch_size].detach().float().cpu()) # ???不知道为什么要这样写
            ret_result.append(
                self.output[idx].detach().float().cpu()
            )  # 原来有错误，本来因该是保存out，这里写成了process的最后一位，现在改回来了
        if self.task in [
            "inpainting",
            "uncropping",
            "my_mission_mask",
            "my_mission_mask_ddim",
        ]:
            ret_path.extend(["Mask_{}".format(name) for name in self.path])
            ret_result.extend(self.mask_image)

        self.results_dict = self.results_dict._replace(name=ret_path, result=ret_result)
        return self.results_dict._asdict()

    def train_step(self):
        self.netG.train()
        self.train_metrics.reset()
        for train_data in tqdm.tqdm(self.phase_loader):
            self.set_input(train_data)
            self.optG.zero_grad()
            # universal_show_img(self.cond_image[0,0,:,:],'gray')
            # universal_show_img(self.gt_image[0,0,:,:],'gray')
            # universal_show_img(self.mask[0,0,:,:],'gray')
            loss = self.netG(self.gt_image, self.cond_image, mask=self.mask)
            loss.backward()
            self.optG.step()

            self.iter += self.batch_size
            self.writer.set_iter(self.epoch, self.iter, phase="train")
            self.train_metrics.update(self.loss_fn.__name__, loss.item())
            if self.iter % self.opt["train"]["log_iter"] == 0:
                for key, value in self.train_metrics.result().items():
                    self.logger.info("{:5s}: {}\t".format(str(key), value))
                    self.writer.add_scalar(key, value)
                for key, value in self.get_current_visuals().items():
                    self.writer.add_images(key, value)
            if self.ema_scheduler is not None:
                if (
                    self.iter > self.ema_scheduler["ema_start"]
                    and self.iter % self.ema_scheduler["ema_iter"] == 0
                ):
                    self.EMA.update_model_average(self.netG_EMA, self.netG)
        self.lr_scheduler.step()
        # print(self.lr_scheduler.get_last_lr())
        # for scheduler in self.schedulers:
        #     scheduler.step()
        return self.train_metrics.result()

    def val_step(self):
        self.netG.eval()
        self.val_metrics.reset()
        with torch.no_grad():
            for val_data in tqdm.tqdm(self.val_loader):
                self.set_input(val_data)
                if self.opt["distributed"]:  # 暂时用不上，这里的restoration先不改
                    if self.task in ["inpainting", "uncropping", "my_mission_mask"]:
                        self.output, self.visuals = self.netG.module.restoration(
                            self.cond_image,
                            y_t=self.cond_image,
                            y_0=self.gt_image,
                            mask=self.mask,
                            sample_num=self.sample_num,
                            target=self.gt_image,
                        )
                    else:
                        self.output, self.visuals = self.netG.module.restoration(
                            self.cond_image,
                            sample_num=self.sample_num,
                            target=self.gt_image,
                        )
                else:
                    if self.task in ["inpainting", "uncropping", "my_mission_mask"]:
                        self.output, self.visuals = self.netG.restoration(
                            self.cond_image,
                            y_t=self.cond_image,
                            y_0=self.gt_image,
                            mask=self.mask,
                            sample_num=self.sample_num,
                            target=self.gt_image,
                        )
                    elif self.task in ["my_mission_mask_ddim"]:
                        self.output, self.visuals = self.netG.restoration_ddim(
                            self.cond_image,
                            y_t=self.cond_image,
                            y_0=self.gt_image,
                            mask=self.mask,
                            sample_num=self.sample_num,
                            target=self.gt_image,
                        )
                    else:
                        self.output, self.visuals = self.netG.restoration(
                            self.cond_image,
                            sample_num=self.sample_num,
                            target=self.gt_image,
                        )  # 我的任务更接近color，所以暂时用这个，这一系列restoration注释进行的同一类修改

                self.iter += self.batch_size
                self.writer.set_iter(self.epoch, self.iter, phase="val")

                for met in self.metrics:
                    key = met.__name__
                    value = met(self.gt_image, self.output)
                    self.val_metrics.update(key, value)
                    self.writer.add_scalar(key, value)
                for key, value in self.get_current_visuals(phase="val").items():
                    self.writer.add_images(key, value)
                self.writer.save_images(self.save_current_results())

        return self.val_metrics.result()

    def test(self):
        self.netG.eval()
        self.test_metrics.reset()
        with torch.no_grad():
            for phase_data in tqdm.tqdm(self.phase_loader):
                self.set_input(phase_data)
                if self.opt["distributed"]:
                    if self.task in ["inpainting", "uncropping", "my_mission_mask"]:
                        self.output, self.visuals = self.netG.module.restoration(
                            self.cond_image,
                            y_t=self.cond_image,
                            y_0=self.gt_image,
                            mask=self.mask,
                            sample_num=self.sample_num,
                            target=self.gt_image,
                        )
                    else:
                        self.output, self.visuals = self.netG.module.restoration(
                            self.cond_image,
                            sample_num=self.sample_num,
                            target=self.gt_image,
                        )
                else:
                    if self.task in ["inpainting", "uncropping", "my_mission_mask"]:
                        self.output, self.visuals = self.netG.restoration(
                            self.cond_image,
                            y_t=self.cond_image,
                            y_0=self.gt_image,
                            mask=self.mask,
                            sample_num=self.sample_num,
                            target=self.gt_image,
                        )
                    elif self.task in ["my_mission_mask_ddim"]:
                        self.output, self.visuals = self.netG.restoration_ddim(
                            self.cond_image,
                            y_t=self.cond_image,
                            y_0=self.gt_image,
                            mask=self.mask,
                            sample_num=self.sample_num,
                            target=self.gt_image,
                        )
                    else:
                        self.output, self.visuals = self.netG.restoration(
                            self.cond_image,
                            sample_num=self.sample_num,
                            target=self.gt_image,
                        )

                self.iter += self.batch_size
                self.writer.set_iter(self.epoch, self.iter, phase="test")
                for met in self.metrics:
                    key = met.__name__
                    value = met(self.gt_image, self.output)
                    self.test_metrics.update(key, value)
                    self.writer.add_scalar(key, value)
                for key, value in self.get_current_visuals(phase="test").items():
                    self.writer.add_images(key, value)
                self.writer.save_images(self.save_current_results())

        test_log = self.test_metrics.result()
        """ save logged informations into log dict """
        test_log.update({"epoch": self.epoch, "iters": self.iter})

        with open("ddim_test.txt", "a") as file:  #
            file.write(self.logger.opt["path"]["resume_state"] + "   ")
            file.write(str(test_log["test/mae"].cpu().numpy()) + "\n")
        """ print logged informations to the screen and tensorboard """
        for key, value in test_log.items():
            self.logger.info("{:5s}: {}\t".format(str(key), value))

    def load_networks(self):
        """save pretrained model and training state, which only do on GPU 0."""
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
        """load pretrained model and training state."""
        if self.opt["distributed"]:
            netG_label = self.netG.module.__class__.__name__
        else:
            netG_label = self.netG.__class__.__name__
        self.save_network(network=self.netG, network_label=netG_label)
        if self.ema_scheduler is not None:
            self.save_network(network=self.netG_EMA, network_label=netG_label + "_ema")
        self.save_training_state()
