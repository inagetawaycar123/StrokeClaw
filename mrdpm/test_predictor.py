import torch
import torch.nn as nn
import numpy as np
import os
import argparse
from tqdm import tqdm
import logging
from datetime import datetime
import json
import shutil
from torch.utils.data import DataLoader


class BRANPredictorTester:
    def __init__(self, config_path, model_path, output_dir):
        """
        BRAN初始预测器测试类
        Args:
            config_path: 配置文件路径
            model_path: 模型权重路径
            output_dir: 输出目录
        """
        self.config_path = config_path
        self.model_path = model_path
        self.output_dir = output_dir
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # 首先设置日志系统，然后再设置目录
        self._setup_logging()
        self._setup_directories()

        # 加载配置和模型
        self.joint_config = self._load_config(config_path)
        self.config = self._extract_test_config(self.joint_config)
        self.model = self._create_model()
        self._load_model_weights(model_path)

        self.logger.info("✅ BRAN预测器测试初始化完成")

    def _load_config(self, config_path):
        """加载配置文件，处理JSON注释"""
        with open(config_path, "r") as f:
            content = f.read()
            # 移除注释
            content = "\n".join([line.split("//")[0] for line in content.split("\n")])
            config = json.loads(content)
        return config

    def _extract_test_config(self, joint_config):
        """从联合训练配置中提取测试所需配置"""
        config = {
            "data_root": joint_config["datasets"]["test"]["which_dataset"]["args"][
                "data_root"
            ],
            "test_list": joint_config["datasets"]["test"]["which_dataset"]["args"][
                "data_flist"
            ],
            "batch_size": joint_config["datasets"]["test"]["dataloader"]["args"][
                "batch_size"
            ],
            "num_workers": joint_config["datasets"]["test"]["dataloader"]["args"][
                "num_workers"
            ],
            "mcta_phase": joint_config["datasets"]["test"]["which_dataset"]["args"].get(
                "mcta_phase", 1
            ),
            "gpu_ids": joint_config.get("gpu_ids", [0]),
        }

        self.logger.info("测试配置提取完成:")
        for key, value in config.items():
            self.logger.info(f"  {key}: {value}")

        return config

    def _create_model(self):
        """创建BRAN网络模型 - 与训练时相同的结构"""
        from models.networks_unet256 import define_G

        # 使用与训练相同的配置
        model = define_G(
            input_nc=3,  # 3通道输入
            output_nc=1,  # 单通道输出
            ngf=32,
            use_dropout=True,
            init_type="kaiming",
            gpu_ids=self.config["gpu_ids"],
        )

        model = model.to(self.device)

        # 多GPU支持
        if len(self.config["gpu_ids"]) > 1:
            model = nn.DataParallel(model, device_ids=self.config["gpu_ids"])
            self.logger.info(f"使用 {len(self.config['gpu_ids'])} 个GPU进行测试")

        return model

    def _load_model_weights(self, model_path):
        """加载模型权重"""
        self.logger.info(f"🔧 加载模型权重: {model_path}")
        # 添加调试信息：输出完整的权重文件地址
        self.logger.info(f"📁 使用的权重文件完整路径: {os.path.abspath(model_path)}")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"模型文件不存在: {model_path}")

        # 检查文件类型
        if model_path.endswith("best_model.pth"):
            # 加载完整检查点
            checkpoint = torch.load(model_path, map_location=self.device)
            if isinstance(self.model, nn.DataParallel):
                self.model.module.load_state_dict(checkpoint["model_state_dict"])
            else:
                self.model.load_state_dict(checkpoint["model_state_dict"])
            self.logger.info(
                f"✅ 从检查点加载权重，epoch: {checkpoint.get('epoch', '未知')}"
            )
        else:
            # 加载纯权重文件
            if isinstance(self.model, nn.DataParallel):
                self.model.module.load_state_dict(
                    torch.load(model_path, map_location=self.device)
                )
            else:
                self.model.load_state_dict(
                    torch.load(model_path, map_location=self.device)
                )
            self.logger.info("✅ 从权重文件加载完成")

        self.model.eval()
        self.logger.info("✅ 模型设置为评估模式")

    def _setup_directories(self):
        """创建输出目录"""
        os.makedirs(self.output_dir, exist_ok=True)
        self.logger.info(f"📁 输出目录: {self.output_dir}")

    def _setup_logging(self):
        """设置日志系统"""
        # 首先创建输出目录（如果不存在）
        os.makedirs(self.output_dir, exist_ok=True)

        log_dir = os.path.join(self.output_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)

        log_file = os.path.join(
            log_dir, f"test_predictor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )

        # 配置日志
        self.logger = logging.getLogger("BRAN_Predictor_Test")
        self.logger.setLevel(logging.INFO)

        # 清除现有处理器
        if self.logger.handlers:
            self.logger.handlers.clear()

        # 文件处理器
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 格式化器
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # 添加处理器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.propagate = False

        self.logger.info("=" * 60)
        self.logger.info("🚀 BRAN初始预测器测试开始")
        self.logger.info(f"📝 日志文件: {log_file}")
        self.logger.info("=" * 60)

    def _create_test_dataloader(self):
        """创建测试数据加载器"""
        from data.dataset import NumpyDataset_mask

        test_dataset = NumpyDataset_mask(
            data_root=self.config["data_root"],
            data_flist=self.config["test_list"],
            data_len=-1,
            mcta_phase=self.config["mcta_phase"],
        )

        test_loader = DataLoader(
            test_dataset,
            batch_size=self.config["batch_size"],
            shuffle=False,
            num_workers=self.config["num_workers"],
            pin_memory=True,
        )

        self.logger.info(f"📊 测试集样本数: {len(test_dataset)}")
        self.logger.info(f"📊 测试批次数: {len(test_loader)}")

        return test_loader

    def _validate_data_shape(self, test_loader):
        """验证测试数据形状"""
        self.logger.info("🔍 验证测试数据形状...")
        sample_batch = next(iter(test_loader))
        cond_shape = sample_batch["cond_image"].shape
        gt_shape = sample_batch["gt_image"].shape

        self.logger.info(f"条件图像形状: {cond_shape}")
        self.logger.info(f"目标图像形状: {gt_shape}")

        if cond_shape[1] != 3:
            self.logger.error(
                f"❌ 测试数据通道数不匹配: 期望3通道，实际{cond_shape[1]}通道"
            )
            raise ValueError("测试数据通道数与模型输入不匹配")

        self.logger.info("✅ 测试数据形状验证通过")
        return sample_batch

    def _get_original_filenames(self, test_loader):
        """获取原始文件名列表"""
        # 从数据加载器获取原始文件名
        if hasattr(test_loader.dataset, "paths"):
            return [os.path.basename(path) for path in test_loader.dataset.paths]
        else:
            # 如果数据集没有paths属性，从文件列表读取
            with open(self.config["test_list"], "r") as f:
                filenames = [line.strip() for line in f.readlines()]
            return filenames

    def test(self):
        """执行测试推理"""
        self.logger.info("🧪 开始测试推理...")

        # 创建数据加载器
        test_loader = self._create_test_dataloader()

        # 验证数据形状
        sample_batch = self._validate_data_shape(test_loader)

        # 获取原始文件名
        original_filenames = self._get_original_filenames(test_loader)

        # 统计信息
        total_samples = 0
        success_count = 0
        error_count = 0

        self.logger.info("🎯 开始推理并保存结果...")

        with torch.no_grad():
            for batch_idx, batch in enumerate(tqdm(test_loader, desc="Testing")):
                # 获取数据
                cond_image = batch["cond_image"].to(self.device)
                gt_image = batch["gt_image"].cpu().numpy()
                mask = batch["mask"].cpu().numpy()

                # 推理
                output, _ = self.model(cond_image)
                pred_image = output.cpu().numpy()

                # ✅ 关键修改：应用掩码到预测结果
                pred_image = pred_image * mask  # 背景区域置零

                # 处理批次中的每个样本
                batch_size = cond_image.size(0)
                for i in range(batch_size):
                    try:
                        # 计算当前样本的全局索引
                        sample_idx = batch_idx * self.config["batch_size"] + i

                        if sample_idx >= len(original_filenames):
                            self.logger.warning(
                                f"⚠️ 样本索引{sample_idx}超出文件列表范围"
                            )
                            continue

                        original_filename = original_filenames[sample_idx]
                        base_name = os.path.splitext(original_filename)[0]

                        # 保存预测结果 (Pre_开头) - 已经应用掩码
                        pred_output = pred_image[i, 0]
                        pred_filename = f"Pre_{base_name}.npy"
                        pred_path = os.path.join(self.output_dir, pred_filename)
                        np.save(pred_path, pred_output)

                        # 保存真实结果 (GT_开头) - 也应用掩码确保一致性
                        gt_output = gt_image[i, 0] * mask[i, 0]
                        gt_filename = f"GT_{base_name}.npy"
                        gt_path = os.path.join(self.output_dir, gt_filename)
                        np.save(gt_path, gt_output)

                        success_count += 1

                    except Exception as e:
                        error_count += 1
                        self.logger.error(f"❌ 处理样本 {sample_idx} 时出错: {str(e)}")

                total_samples += batch_size

        # ✅ 关键修复：添加统计结果输出和返回语句
        self.logger.info("=" * 60)
        self.logger.info("📊 测试推理完成统计:")
        self.logger.info(f"总样本数: {total_samples}")
        self.logger.info(f"成功处理: {success_count}")
        self.logger.info(f"处理失败: {error_count}")
        if total_samples > 0:
            self.logger.info(f"成功率: {success_count / total_samples * 100:.2f}%")
        else:
            self.logger.info("成功率: 0.00% (无样本处理)")
        self.logger.info(f"输出目录: {self.output_dir}")
        self.logger.info("=" * 60)

        # 保存测试配置摘要
        self._save_test_summary(success_count, error_count, total_samples)

        # ✅ 关键修复：返回统计结果
        return success_count, error_count

    def _simple_ssim(self, pred, gt, data_range):
        """简化的SSIM计算实现"""
        # 如果数据量太小，返回默认值
        if len(pred) < 2 or len(gt) < 2:
            return 1.0

        # 计算均值
        mu_x = np.mean(pred)
        mu_y = np.mean(gt)

        # 计算方差和协方差
        sigma_x = np.std(pred)
        sigma_y = np.std(gt)
        sigma_xy = np.cov(pred, gt)[0, 1] if len(pred) > 1 else 0

        # SSIM常数
        C1 = (0.01 * data_range) ** 2
        C2 = (0.03 * data_range) ** 2

        # 计算SSIM
        ssim_numerator = (2 * mu_x * mu_y + C1) * (2 * sigma_xy + C2)
        ssim_denominator = (mu_x**2 + mu_y**2 + C1) * (sigma_x**2 + sigma_y**2 + C2)

        if ssim_denominator == 0:
            return 1.0

        return ssim_numerator / ssim_denominator

    def _save_test_summary(self, success_count, error_count, total_samples):
        """保存测试摘要"""
        summary = {
            "test_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "model_path": self.model_path,
            "config_path": self.config_path,
            "output_dir": self.output_dir,
            "total_samples": total_samples,
            "success_count": success_count,
            "error_count": error_count,
            "success_rate": success_count / total_samples * 100,
            "device": str(self.device),
            "test_config": {
                "data_root": self.config["data_root"],
                "test_list": self.config["test_list"],
                "batch_size": self.config["batch_size"],
                "mcta_phase": self.config["mcta_phase"],
            },
        }

        summary_path = os.path.join(self.output_dir, "test_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        self.logger.info(f"📄 测试摘要已保存: {summary_path}")

    def calculate_metrics(self):
        """计算预测结果与真实结果之间的指标"""
        self.logger.info("📈 开始计算评估指标...")

        # 收集所有预测和真实文件
        pred_files = [
            f
            for f in os.listdir(self.output_dir)
            if f.startswith("Pre_") and f.endswith(".npy")
        ]
        gt_files = [
            f
            for f in os.listdir(self.output_dir)
            if f.startswith("GT_") and f.endswith(".npy")
        ]

        if not pred_files or not gt_files:
            self.logger.warning("⚠️ 未找到预测结果或真实结果文件")
            return None

        # 确保文件匹配
        pred_files.sort()
        gt_files.sort()

        metrics = {
            "mae": 0.0,
            "mse": 0.0,
            "psnr": 0.0,
            "ssim": 0.0,
            "processed_count": 0,
        }

        for pred_file, gt_file in zip(pred_files, gt_files):
            try:
                # 验证文件名对应关系
                pred_base = pred_file[4:]  # 去掉"Pre_"
                gt_base = gt_file[3:]  # 去掉"GT_"

                if pred_base != gt_base:
                    self.logger.warning(f"⚠️ 文件不匹配: {pred_file} vs {gt_file}")
                    continue

                # 加载数据
                pred = np.load(os.path.join(self.output_dir, pred_file))
                gt = np.load(os.path.join(self.output_dir, gt_file))

                # 创建简单的脑部掩码（基于非零值）
                brain_mask = (gt > 0) | (pred > 0)

                # 只在脑部区域计算指标
                if brain_mask.sum() > 0:
                    pred_brain = pred[brain_mask]
                    gt_brain = gt[brain_mask]

                    mae = np.mean(np.abs(pred_brain - gt_brain))
                    mse = np.mean((pred_brain - gt_brain) ** 2)

                    # 计算PSNR和SSIM
                    data_range = gt_brain.max() - gt_brain.min()
                    if data_range > 0 and mse > 0:
                        psnr_val = 20 * np.log10(data_range / np.sqrt(mse))
                        ssim_val = self._simple_ssim(pred_brain, gt_brain, data_range)
                    else:
                        psnr_val = float("inf")
                        ssim_val = 1.0
                else:
                    mae = mse = 0.0
                    psnr_val = float("inf")
                    ssim_val = 1.0

                metrics["mae"] += mae
                metrics["mse"] += mse
                metrics["psnr"] += psnr_val
                metrics["ssim"] += ssim_val
                metrics["processed_count"] += 1

            except Exception as e:
                self.logger.error(f"❌ 计算指标时出错 {pred_file}: {str(e)}")
                continue

        if metrics["processed_count"] > 0:
            # 计算平均值
            for key in ["mae", "mse", "psnr", "ssim"]:
                metrics[key] /= metrics["processed_count"]

            self.logger.info("📊 评估指标结果:")
            self.logger.info(f"  MAE: {metrics['mae']:.6f}")
            self.logger.info(f"  MSE: {metrics['mse']:.6f}")
            self.logger.info(f"  PSNR: {metrics['psnr']:.2f} dB")
            self.logger.info(f"  SSIM: {metrics['ssim']:.4f}")
            self.logger.info(f"  有效样本数: {metrics['processed_count']}")

            # 保存指标到文件
            metrics_path = os.path.join(self.output_dir, "test_metrics.json")
            with open(metrics_path, "w", encoding="utf-8") as f:
                json.dump(metrics, f, indent=2, ensure_ascii=False)
            self.logger.info(f"📄 指标结果已保存: {metrics_path}")

        return metrics


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="BRAN初始预测器测试脚本")
    parser.add_argument("--config", type=str, required=True, help="配置文件路径")
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="模型权重路径 (best_model.pth 或 bran_pretrained_3channel.pth)",
    )
    parser.add_argument("--output", type=str, required=True, help="输出目录路径")
    parser.add_argument(
        "--calculate_metrics", action="store_true", help="是否计算评估指标"
    )

    args = parser.parse_args()

    # 验证输入参数
    if not os.path.exists(args.config):
        print(f"❌ 配置文件不存在: {args.config}")
        return

    if not os.path.exists(args.model):
        print(f"❌ 模型文件不存在: {args.model}")
        return

    try:
        # 创建测试器
        tester = BRANPredictorTester(args.config, args.model, args.output)

        # 执行测试
        success_count, error_count = tester.test()

        # 可选：计算评估指标
        if args.calculate_metrics:
            tester.calculate_metrics()

        print(f"🎉 测试完成！成功处理 {success_count} 个样本，失败 {error_count} 个")
        print(f"📁 结果保存在: {args.output}")

    except Exception as e:
        print(f"❌ 测试过程中发生错误: {str(e)}")
        # 可以选择记录更详细的错误信息
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
