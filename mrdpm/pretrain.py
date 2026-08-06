import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
import torch.nn.functional as F
import os
import numpy as np
from tqdm import tqdm
import logging
from datetime import datetime
import json


class BRANPretrainer:
    def __init__(self, joint_config):
        """
        BRAN网络预训练器 - 专门用于初始预测器的预训练
        Args:
            joint_config: 完整的MRDPM联合训练配置文件
        """
        # 首先设置基本目录和日志系统
        self.joint_config = joint_config
        self.config = self._extract_bran_config(joint_config)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # 提前创建目录和日志系统
        self._setup_directories()
        self._setup_logging()  # 提前设置日志

        self.logger.info("🚀 开始初始化BRAN预训练器")

        # 然后创建其他组件
        self.model = self._create_model()
        self.optimizer = self._create_optimizer()
        self.criterion = nn.L1Loss()

        # 训练状态
        self.current_epoch = 0
        self.best_val_loss = float("inf")

        self.logger.info("✅ BRAN预训练器初始化完成")

    def _extract_bran_config(self, joint_config):
        """从联合训练配置中提取BRAN预训练所需配置"""
        config = {
            "save_dir": "./experiments/bran_pretrain_3channel",
            "epochs": joint_config["train"]["n_epoch"],
            "optimizer": {
                "type": "adam",
                "lr": joint_config["model"]["which_model"]["args"]["optimizers"][0][
                    "lr"
                ],
                "weight_decay": joint_config["model"]["which_model"]["args"][
                    "optimizers"
                ][0].get("weight_decay", 0),
                "beta1": 0.9,
                "beta2": 0.999,
            },
            "batch_size": joint_config["datasets"]["train"]["dataloader"]["args"][
                "batch_size"
            ],
            "data_root": joint_config["datasets"]["train"]["which_dataset"]["args"][
                "data_root"
            ],
            "train_list": joint_config["datasets"]["train"]["which_dataset"]["args"][
                "data_flist"
            ],
            # 验证集配置
            "val_list": joint_config["datasets"]["train"]["which_dataset"]["args"][
                "data_flist"
            ].replace("train", "val"),
            "num_workers": joint_config["datasets"]["train"]["dataloader"]["args"][
                "num_workers"
            ],
            "validation_split": joint_config["datasets"]["train"]["dataloader"].get(
                "validation_split", 10
            ),  # 作为样本数目
            "save_interval": joint_config["train"].get(
                "save_checkpoint_epoch", 10
            ),  # 改为1，每个epoch都保存
            "log_iter": joint_config["train"].get("log_iter", 2000),
            # 从配置中提取mcta_phase参数
            "mcta_phase": joint_config["datasets"]["train"]["which_dataset"][
                "args"
            ].get("mcta_phase", 1),
            # 添加验证频率配置
            "val_epoch": joint_config["train"].get(
                "val_epoch", 10
            ),  # 从配置中读取验证频率
            # 关键修改：添加验证集batch_size配置
            "val_batch_size": joint_config["datasets"]["train"]["dataloader"][
                "val_args"
            ]["batch_size"],
            # 验证集batch_size=1
        }

        # 日志记录提取的配置
        logging.info("BRAN预训练配置提取完成:")
        for key, value in config.items():
            if key != "optimizer":
                logging.info(f"  {key}: {value}")
            else:
                logging.info(f"  {key}: {value}")

        return config

    def _create_model(self):
        """创建BRAN网络模型 - 关键修改：输入通道改为3"""
        from models.networks_unet256 import define_G

        # 关键修改：input_nc改为3，匹配您的3通道输入数据
        # 预训练阶段只需要条件图像，不需要掩码通道
        model = define_G(
            input_nc=3,  # ✅ 3通道：NCCT + mCTA动脉期 + 全零通道
            output_nc=1,  # 输出CTP图像（单通道）
            ngf=32,  # 特征图基础通道数
            use_dropout=True,
            init_type="kaiming",
            gpu_ids=self.joint_config["gpu_ids"],
        )

        model = model.to(self.device)

        # 多GPU训练支持
        if len(self.joint_config["gpu_ids"]) > 1:
            model = nn.DataParallel(model, device_ids=self.joint_config["gpu_ids"])
            logging.info(f"使用 {len(self.joint_config['gpu_ids'])} 个GPU进行训练")

        return model

    def _create_optimizer(self):
        """创建优化器"""
        optimizer_config = self.config["optimizer"]

        if optimizer_config["type"] == "adam":
            return optim.Adam(
                self.model.parameters(),
                lr=optimizer_config["lr"],
                betas=(
                    optimizer_config.get("beta1", 0.9),
                    optimizer_config.get("beta2", 0.999),
                ),
                weight_decay=optimizer_config.get("weight_decay", 0),
            )
        else:
            return optim.Adam(
                self.model.parameters(),
                lr=optimizer_config["lr"],
                weight_decay=optimizer_config.get("weight_decay", 0),
            )

    def _create_scheduler(self):
        """创建学习率调度器"""
        return optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="min", factor=0.5, patience=5
        )

    def _setup_directories(self):
        """创建保存目录"""
        self.save_dir = self.config["save_dir"]
        os.makedirs(os.path.join(self.save_dir, "checkpoints"), exist_ok=True)
        os.makedirs(os.path.join(self.save_dir, "logs"), exist_ok=True)
        os.makedirs(os.path.join(self.save_dir, "tensorboard"), exist_ok=True)

    def _setup_logging(self):
        """设置日志系统 - 修复日志文件为空的问题"""
        # 创建日志目录
        log_dir = os.path.join(self.save_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)

        log_file = os.path.join(
            log_dir,
            f"bran_pretrain_3channel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        )

        # 清除任何现有的日志配置
        logging.root.handlers = []

        # 创建格式化器
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

        # 创建文件处理器并设置级别
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)

        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        # 获取或创建日志器 - 先初始化logger
        self.logger = logging.getLogger("BRAN_Pretrain_3Channel")
        self.logger.setLevel(logging.INFO)

        # 清除任何现有的处理器（避免重复记录）
        if self.logger.handlers:
            self.logger.handlers.clear()

        # 添加处理器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        # 确保传播到根日志器（可选，根据需求）
        self.logger.propagate = False

        # 现在检查日志文件权限 - 在logger初始化后调用
        self._check_log_file_permissions(log_file)

        # 立即记录一条测试消息
        self.logger.info("=" * 60)
        self.logger.info("📝 日志系统初始化成功")
        self.logger.info(f"📁 日志极速文件: {log_file}")
        self.logger.info("=" * 60)

        # 强制刷新以确保消息写入文件
        for handler in self.logger.handlers:
            handler.flush()

        # 也配置根日志器以备不时之需
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[file_handler, console_handler],
        )

        # 测试日志系统
        self._test_logging_system()

    def _check_log_file_permissions(self, log_file):
        """检查日志文件是否可写"""
        try:
            # 尝试写入测试消息
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now()} - 权限测试消息\n")

            # 使用print而不是logger，因为logger可能尚未完全初始化
            print(f"✅ 日志文件可写: {log_file}")
            return True
        except IOError as e:
            print(f"❌ 日志文件无法写入: {e}")
            # 尝试创建目录后重试
            try:
                os.makedirs(os.path.dirname(log_file), exist_ok=True)
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now()} - 权限测试消息（目录已创建）\n")
                print(f"✅ 已创建目录并验证日志文件可写: {log_file}")
                return True
            except IOError as e2:
                print(f"❌ 仍然无法写入日志文件: {e2}")
                return False

    def _test_logging_system(self):
        """测试日志系统是否正常工作"""
        test_messages = [
            "🔧 测试日志系统 - 调试级别",
            "📋 测试日志系统 - 信息级别",
            "⚠️  测试日志系统 - 警告级别",
            "❌ 测试日志系统 - 错误级别",
        ]

        self.logger.debug(test_messages[0])
        self.logger.info(test_messages[1])
        self.logger.warning(test_messages[2])
        self.logger.error(test_messages[3])

        # 立即刷新
        for handler in self.logger.handlers:
            handler.flush()

        self.logger.info("✅ 日志系统测试完成")

    def _create_dataloaders(self):
        """创建数据加载器 - 使用您修改后的NumpyDataset_mask，支持验证集自动划分"""
        from data.dataset import NumpyDataset_mask

        # 训练数据集
        train_dataset = NumpyDataset_mask(
            data_root=self.config["data_root"],
            data_flist=self.config["train_list"],
            data_len=-1,
            mcta_phase=self.config["mcta_phase"],  # 传递时相选择参数
        )

        # 验证数据集处理逻辑
        val_loader = None
        validation_split = self.config["validation_split"]

        # 首先尝试使用单独的验证集文件
        if os.path.exists(self.config["val_list"]):
            self.logger.info("✅ 使用单独的验证集文件")
            val_dataset = NumpyDataset_mask(
                data_root=self.config["data_root"],
                data_flist=self.config["val_list"],
                data_len=-1,
                mcta_phase=self.config["mcta_phase"],
            )

            # 关键修改：使用验证集专用的batch_size=1
            val_loader = DataLoader(
                val_dataset,
                batch_size=self.config["val_batch_size"],  # ✅ 使用验证集batch_size=1
                shuffle=False,
                num_workers=self.config["num_workers"],
                pin_memory=True,
            )

            # 使用完整的训练集
            train_loader = DataLoader(
                train_dataset,
                batch_size=self.config["batch_size"],  # 训练集batch_size=4
                shuffle=True,
                num_workers=self.config["num_workers"],
                pin_memory=True,
            )

        elif validation_split > 0:
            # 从训练集中自动划分验证集 - 使用validation_split作为样本数目
            total_size = len(train_dataset)

            # 确保验证集样本数不超过总样本数
            if validation_split >= total_size:
                self.logger.warning(
                    f"⚠️ 验证集样本数({validation_split})大于等于总样本数({total_size})，使用总样本数-1作为验证集"
                )
                val_size = total_size - 1
                train_size = 1
            else:
                val_size = validation_split
                train_size = total_size - val_size

            self.logger.info(f"🔧 从训练集中自动划分{val_size}个样本作为验证集")

            # 随机划分训练集和验证集
            train_subset, val_subset = random_split(
                train_dataset,
                [train_size, val_size],
                generator=torch.Generator().manual_seed(42),  # 固定随机种子保证可重复性
            )

            self.logger.info(f"训练集样本数: {train_size}, 验证集样本数: {val_size}")

            train_loader = DataLoader(
                train_subset,
                batch_size=self.config["batch_size"],  # 训练集batch_size=4
                shuffle=True,
                num_workers=self.config["num_workers"],
                pin_memory=True,
            )

            # 关键修改：使用验证集专用的batch_size=1
            val_loader = DataLoader(
                val_subset,
                batch_size=self.config["val_batch_size"],  # ✅ 使用验证集batch_size=1
                shuffle=False,
                num_workers=self.config["num_workers"],
                pin_memory=True,
            )
        else:
            # 没有验证集，只进行训练
            self.logger.warning("⚠️ 没有验证集，将只进行训练")

            train_loader = DataLoader(
                train_dataset,
                batch_size=self.config["batch_size"],
                shuffle=True,
                num_workers=self.config["num_workers"],
                pin_memory=True,
            )

        return train_loader, val_loader

    def _validate_data_shape(self, train_loader):
        """验证数据形状是否与模型匹配"""
        self.logger.info("正在进行数据形状验证...")
        sample_batch = next(iter(train_loader))
        cond_shape = sample_batch["cond_image"].shape
        gt_shape = sample_batch["gt_image"].shape

        self.logger.info(f"条件图像形状: {cond_shape} [批次大小, 通道数, 高度, 宽度]")
        self.logger.info(f"目标图像形状: {gt_shape}")

        # 验证通道数匹配
        if cond_shape[1] != 3:
            self.logger.error(
                f"❌ 数据通道数不匹配: 期望3通道，实际{cond_shape[1]}通道"
            )
            raise ValueError("数据通道数与模型输入不匹配")

        self.logger.info("✅ 数据形状验证通过")

    def train_epoch(self, train_loader):
        """训练一个epoch"""
        self.model.train()
        total_loss = 0
        num_batches = len(train_loader)

        progress_bar = tqdm(train_loader, desc=f"Epoch {self.current_epoch} Training")

        for batch_idx, batch in enumerate(progress_bar):
            # 获取数据 - 3通道条件图像
            cond_image = batch["cond_image"].to(self.device)  # 3通道mCTA图像
            gt_image = batch["gt_image"].to(self.device)  # 真实CTP图像
            mask = batch["mask"].to(self.device)  # 脑部掩码

            # 前向传播 - 对应论文中的 x_init = I_θ(y)
            self.optimizer.zero_grad()
            output, _ = self.model(cond_image)  # BRAN网络输出

            # 应用掩码，只计算脑部区域的损失
            masked_output = output * mask
            masked_gt = gt_image * mask

            # 计算损失 - 对应论文公式(1): L_init = E‖x_gt - x_init‖₁
            loss = self.criterion(masked_output, masked_gt)

            # 反向传播
            loss.backward()

            # 梯度裁剪
            if self.joint_config["train"].get("grad_clip"):
                torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(), self.joint_config["train"]["grad_clip"]
                )

            self.optimizer.step()

            total_loss += loss.item()

            # 定期记录日志
            if batch_idx % self.config["log_iter"] == 0:
                self.logger.info(
                    f"Epoch {self.current_epoch} Batch {batch_idx}: Loss = {loss.item():.6f}"
                )

            # 定期刷新日志
            if batch_idx % 100 == 0:  # 每100个批次刷新一次
                for handler in self.logger.handlers:
                    if isinstance(handler, logging.FileHandler):
                        handler.flush()

            # 更新进度条
            progress_bar.set_postfix(
                {
                    "Loss": f"{loss.item():.6f}",
                    "Avg Loss": f"{total_loss / (batch_idx + 1):.6f}",
                }
            )

        avg_loss = total_loss / num_batches
        return avg_loss

    def validate(self, val_loader):
        """验证模型"""
        if val_loader is None:
            self.logger.info("🔄 跳过验证（无验证集）")
            return float("inf"), float("inf")

        self.model.eval()
        total_loss = 0
        total_mae = 0
        total_samples = 0

        self.logger.info("🔍 开始验证...")
        with torch.no_grad():
            for batch_idx, batch in enumerate(tqdm(val_loader, desc="Validating")):
                cond_image = batch["cond_image"].to(self.device)
                gt_image = batch["gt_image"].to(self.device)
                mask = batch["mask"].to(self.device)

                output, _ = self.model(cond_image)

                # 应用掩码
                masked_output = output * mask
                masked_gt = gt_image * mask

                loss = self.criterion(masked_output, masked_gt)
                mae = F.l1_loss(masked_output, masked_gt)

                total_loss += loss.item() * cond_image.size(0)
                total_mae += mae.item() * cond_image.size(0)
                total_samples += cond_image.size(0)

        avg_loss = total_loss / total_samples
        avg_mae = total_mae / total_samples

        # 关键修改：增强验证结果日志输出
        self.logger.info(
            f"📊 验证完成 - 样本数: {total_samples}, 批次: {len(val_loader)}"
        )
        self.logger.info(f"📈 验证损失: {avg_loss:.6f}, MAE: {avg_mae:.6f}")

        return avg_loss, avg_mae

    def save_checkpoint(self, is_best=False):
        """保存检查点"""
        checkpoint = {
            "epoch": self.current_epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "best_val_loss": self.best_val_loss,
            "config": self.config,
            "joint_config": self.joint_config,
        }

        # 保存当前epoch的检查点
        checkpoint_path = os.path.join(
            self.save_dir, "checkpoints", f"checkpoint_epoch_{self.current_epoch}.pth"
        )
        torch.save(checkpoint, checkpoint_path)

        # 如果是最佳模型，额外保存
        if is_best:
            best_path = os.path.join(self.save_dir, "checkpoints", "best_model.pth")
            torch.save(checkpoint, best_path)

            # 保存用于扩散模型的权重
            diffusion_ready_path = os.path.join(
                self.save_dir, "checkpoints", "brain_pretrained_3channel.pth"
            )

            # 保存模型状态字典
            if isinstance(self.model, nn.DataParallel):
                torch.save(self.model.module.state_dict(), diffusion_ready_path)
            else:
                torch.save(self.model.state_dict(), diffusion_ready_path)

            self.logger.info(f"✅ 预训练权重已保存: {diffusion_ready_path}")

    def load_checkpoint(self, checkpoint_path):
        """加载检查点"""
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.current_epoch = checkpoint["epoch"]
        self.best_val_loss = checkpoint["best_val_loss"]

        self.logger.info(f"加载检查点: {checkpoint_path}")
        self.logger.info(f"从epoch {self.current_epoch}继续训练")

    def train(self):
        """完整的训练流程"""
        self.logger.info("🚀 开始BRAN网络预训练（3通道输入版本）")
        self.logger.info(f"总训练轮数: {self.config['epochs']}")
        self.logger.info(f"批量大小: {self.config['batch_size']}")
        self.logger.info(f"学习率: {self.config['optimizer']['lr']}")
        self.logger.info(f"验证频率: 每{self.config['val_epoch']}个epoch验证一次")
        self.logger.info(f"验证集样本数: {self.config['validation_split']}个样本")
        self.logger.info(f"验证集batch_size: {self.config['val_batch_size']}")

        # 创建数据加载器
        train_loader, val_loader = self._create_dataloaders()
        self.logger.info(f"训练样本数: {len(train_loader.dataset)}")
        if val_loader:
            self.logger.info(f"验证样本数: {len(val_loader.dataset)}")
            # 关键修改：显示验证集批次信息
            expected_batches = len(val_loader.dataset) // self.config["val_batch_size"]
            self.logger.info(
                f"预期验证批次: {expected_batches} (样本数{len(val_loader.dataset)} ÷ batch_size{self.config['val_batch_size']})"
            )
        else:
            self.logger.info("验证样本数: 0 (无验证集)")

        # 验证数据形状
        self._validate_data_shape(train_loader)

        scheduler = self._create_scheduler()

        for epoch in range(self.current_epoch, self.config["epochs"]):
            self.current_epoch = epoch

            # 训练
            self.logger.info(f"🏃‍♂️ 开始Epoch {epoch}训练")
            train_loss = self.train_epoch(train_loader)
            self.logger.info(f"Epoch {epoch}: 训练损失 = {train_loss:.6f}")

            # 验证 - 根据配置的频率进行验证
            if epoch % self.config["val_epoch"] == 0:
                self.logger.info(f"🔍 进行Epoch {epoch}验证")
                val_loss, val_mae = self.validate(val_loader)

                if val_loader is not None:
                    # 关键修改：增强验证结果显示
                    self.logger.info("=" * 60)
                    self.logger.info(f"📊 Epoch {epoch} 验证结果:")
                    self.logger.info(f"  训练损失: {train_loss:.6f}")
                    self.logger.info(f"  验证损失: {val_loss:.6f}")
                    self.logger.info(f"  MAE指标: {val_mae:.6f}")
                    self.logger.info("=" * 60)

                    # 更新学习率
                    if scheduler:
                        scheduler.step(val_loss)

                    # 保存最佳模型
                    if val_loss < self.best_val_loss:
                        self.best_val_loss = val_loss
                        self.save_checkpoint(is_best=True)
                        self.logger.info(f"🎯 新的最佳模型，验证损失: {val_loss:.6f}")
                else:
                    self.logger.info(f"Epoch {epoch}: 无验证集，跳过验证步骤")
            else:
                self.logger.info(
                    f"⏭️  Epoch {epoch}跳过验证（验证频率: 每{self.config['val_epoch']}个epoch）"
                )

            # 定期保存检查点
            if epoch % self.config["save_interval"] == 0:
                self.save_checkpoint()
                self.logger.info(f"💾 Epoch {epoch}检查点已保存")

        self.logger.info("✅ BRAN网络预训练完成")

        # 返回最佳模型路径
        final_model_path = os.path.join(
            self.save_dir, "checkpoints", "bran_pretrained_3channel.pth"
        )
        self.logger.info(f"预训练权重保存路径: {final_model_path}")
        return final_model_path


def load_config(config_path):
    """加载配置文件，处理JSON注释"""
    with open(config_path, "r") as f:
        content = f.read()
        # 移除注释
        content = "\n".join([line.split("//")[0] for line in content.split("\n")])
        config = json.loads(content)
    return config


if __name__ == "__main__":
    # 加载联合训练配置文件
    config_path = "./config/npy_1000linear_-6_-2_b4_nc64.json"
    joint_config = load_config(config_path)

    # 检查配置中的in_channel（仅供提示，不影响预训练）
    unet_in_channel = joint_config["model"]["which_networks"][0]["args"]["unet"][
        "in_channel"
    ]
    print(f"📝 配置文件中的unet.in_channel: {unet_in_channel}")
    print("💡 注意：预训练使用独立的输入通道设置（3通道），不影响联合训练配置")

    # 创建并运行预训练
    trainer = BRANPretrainer(joint_config)

    # 开始训练
    best_model_path = trainer.train()
    print(f"🎉 预训练完成，模型保存在: {best_model_path}")
