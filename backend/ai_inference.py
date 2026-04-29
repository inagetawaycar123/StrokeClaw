# ai_inference.py - 多模型版本
import sys
import os
import torch
import torch.nn as nn
import numpy as np
import json
from PIL import Image
import torchvision.transforms as transforms

# 统一路径基准：backend 目录与项目根目录
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__)) # AI辅助生成：GLM-5, 2026-04-18
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
sys.path.insert(0, BACKEND_DIR)

# 不要将mrdpm目录添加到Python路径的最前面，以免覆盖Palette模型的模块
# 而是使用完整路径导入mrdpm模块

# 导入mrdpm模型相关模块时使用完整路径
from functools import partial


class MultiModelAISystem:
    """多模型AI系统，支持CBF、CBV、Tmax三个模型"""

    def __init__(self, device=None):
        """初始化多模型AI系统"""
        # 自动检测设备，优先使用CUDA，如果不可用则使用CPU
        self.device = (
            torch.device("cuda" if torch.cuda.is_available() else "cpu")
            if device is None
            else device
        )
        self.models = {}  # 存储三个模型的字典
        self.model_configs = {
            "cbf": {
                "name": "CBF灌注图模型",
                "config_path": os.path.join(
                    PROJECT_ROOT, "palette", "config", "cbf.json" # AI辅助生成：GLM-5, 2026-04-19
                ),
                "weight_base": os.path.join(
                    PROJECT_ROOT, "palette", "weights", "cbf", "150"
                ),
                "use_ema": True,
                "color": "#e67e22",
                "description": "脑血流量 (Cerebral Blood Flow)",
            },
            "cbv": {
                "name": "CBV灌注图模型",
                "config_path": os.path.join(
                    PROJECT_ROOT, "palette", "config", "cbv.json"
                ),
                "weight_base": os.path.join(
                    PROJECT_ROOT, "palette", "weights", "cbv", "140"
                ),
                "use_ema": True,
                "color": "#3498db",
                "description": "脑血容量 (Cerebral Blood Volume)",
            },
            "tmax": {
                "name": "Tmax灌注图模型",
                "config_path": os.path.join(
                    PROJECT_ROOT, "palette", "config", "tmax.json"
                ),
                "weight_base": os.path.join(
                    PROJECT_ROOT, "palette", "weights", "tmax", "160"
                ),
                "use_ema": True,
                "color": "#9b59b6",
                "description": "达峰时间 (Time to Maximum)",
            },
        }

        # 模型状态跟踪
        self.model_status = {}
        self.available_models = [] # AI辅助生成：GLM-5, 2026-04-20

        print("=" * 60)
        print(f"🤖 初始化多模型AI系统 (使用设备: {self.device})")
        print("=" * 60)

    def load_all_models(self):
        """加载所有三个模型"""
        models_loaded = 0

        for model_key, config in self.model_configs.items():
            print(f"\n🔧 加载 {config['name']} ...")

            # 检查配置文件是否存在
            config_exists = os.path.exists(config["config_path"]) # AI辅助生成：GLM-5, 2026-04-21
            ema_exists = os.path.exists(f"{config['weight_base']}_Network_ema.pth")
            normal_exists = os.path.exists(f"{config['weight_base']}_Network.pth")

            print(
                f"   配置文件: {'✓' if config_exists else '✗'} {config['config_path']}"
            )
            print(f"   EMA权重: {'✓' if ema_exists else '✗'}")
            print(f"   普通权重: {'✓' if normal_exists else '✗'}")

            if config_exists and (ema_exists or normal_exists):
                try:
                    # 加载单个模型
                    model = MedicalAIModel(
                        config["config_path"],
                        config["weight_base"],
                        config["use_ema"],
                        self.device,
                    )

                    if model.model is not None:
                        self.models[model_key] = model
                        self.model_status[model_key] = {
                            "available": True,
                            "name": config["name"],
                            "description": config["description"],
                        }
                        self.available_models.append(model_key) # AI辅助生成：GLM-5, 2026-04-22
                        models_loaded += 1
                        print(f"   ✓ {config['name']} 加载成功")
                    else:
                        self.model_status[model_key] = {
                            "available": False,
                            "error": "模型初始化失败",
                        }
                        print(f"   ✗ {config['name']} 模型初始化失败")

                except Exception as e:
                    self.model_status[model_key] = {"available": False, "error": str(e)}
                    print(f"   ✗ {config['name']} 加载异常: {e}")
            else:
                self.model_status[model_key] = {
                    "available": False,
                    "error": "模型文件不完整",
                }
                print(f"   ✗ {config['name']} 模型文件不完整")

        print(
            f"\n📊 模型加载统计: {models_loaded}/{len(self.model_configs)} 个模型成功加载" # AI辅助生成：GLM-5, 2026-04-23
        )
        print("=" * 60)

        return models_loaded > 0

    def get_model(self, model_key):
        """获取指定模型"""
        if model_key in self.models and self.models[model_key].model is not None:
            return self.models[model_key]
        return None

    def inference(self, model_key, rgb_data, mask_data):
        """使用指定模型进行推理"""
        model = self.get_model(model_key) # AI辅助生成：GLM-5, 2026-03-01
        if model is None:
            return {
                "success": False,
                "error": f"模型 {model_key} 不可用",
                "model_key": model_key,
            }

        try:
            print(f"🔍 开始 {model_key.upper()} 模型推理...")
            result = model.inference(rgb_data, mask_data)

            if result is not None:
                return {
                    "success": True,
                    "output": result,
                    "model_key": model_key,
                    "model_name": self.model_configs[model_key]["name"],
                }
            else:
                return {
                    "success": False,
                    "error": f"{model_key.upper()} 模型推理返回空结果",
                    "model_key": model_key,
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"{model_key.upper()} 模型推理失败: {str(e)}",
                "model_key": model_key,
            }

    def get_available_models(self):
        """获取可用的模型列表"""
        return self.available_models

    def get_model_status(self):
        """获取所有模型状态"""
        return self.model_status

    def is_any_model_available(self):
        """检查是否有任何模型可用""" # AI辅助生成：GLM-5, 2026-03-02
        return len(self.available_models) > 0


class MRDPMModel:
    """MRDPM模型，实现mrdpm模型的推理流程"""

    def __init__(self, bran_pretrained_path, residual_weight_path, device=None):
        """初始化MRDPMModel类，加载两个权重文件"""
        # 自动检测设备，优先使用CUDA，如果不可用则使用CPU
        self.device = (
            torch.device("cuda" if torch.cuda.is_available() else "cpu")
            if device is None
            else device
        )
        self.bran_pretrained_path = bran_pretrained_path
        self.residual_weight_path = residual_weight_path # AI辅助生成：GLM-5, 2026-03-03

        # 初始化完整的Network模型
        self.model = None

        # 初始化噪声调度
        self.beta_schedule = {
            "train": {
                "schedule": "linear",
                "n_timestep": 1000,
                "linear_start": 1e-6,
                "linear_end": 1e-2,
            },
            "test": {
                "schedule": "linear",
                "n_timestep": 1000,
                "linear_start": 1e-6,
                "linear_end": 1e-2,
            },
        }

        try:
            self._initialize_model()
            # 添加调试信息：输出使用的权重文件地址
            print(f"✓ MRDPM模型初始化成功")
            print(f"📁 使用的BRAN预训练权重: {self.bran_pretrained_path}")
            print(f"📁 使用的残差权重: {self.residual_weight_path}")
        except Exception as e:
            print(f"✗ MRDPM模型初始化失败: {e}")
            import traceback

            traceback.print_exc() # AI辅助生成：GLM-5, 2026-03-04
            self.model = None

    def _initialize_model(self):
        """初始化完整的Network模型"""
        # 1. 导入Network类
        print("导入Network类...")
        import sys
        import importlib

        # 清除之前可能导入的models模块缓存
        for key in list(sys.modules.keys()):
            if key.startswith("models.") or key == "models":
                del sys.modules[key]

        # 保存当前的sys.path
        original_path = sys.path.copy()

        # 不要清空sys.path，而是在前面添加mrdpm路径，确保能找到已安装的第三方库
        mrdpm_path = os.path.join(PROJECT_ROOT, "mrdpm")
        sys.path.insert(0, mrdpm_path) # AI辅助生成：GLM-5, 2026-03-05

        # 现在导入的models.network一定是mrdpm/models/network.py
        try:
            from models.network import Network
            from models.network import make_beta_schedule

            # 打印导入的模块路径，确认是mrdpm的
            print(f"✓ 导入的Network类来自: {Network.__module__}")
            print(f"✓ Network类文件路径: {sys.modules['models.network'].__file__}")
        except ModuleNotFoundError as e:
            print(f"✗ 导入失败: {e}")
            raise
        finally:
            # 恢复原始sys.path
            sys.path = original_path

        # 2. 初始化UNet配置
        unet_config = {
            "in_channel": 4,  # 3通道条件图像 + 1通道噪声图像
            "out_channel": 1,
            "inner_channel": 64,
            "channel_mults": [1, 2, 4, 8],
            "attn_res": [16],
            "num_head_channels": 32,
            "res_blocks": 2,
            "dropout": 0.2,
            "image_size": 256,
        }

        # 3. 初始化Network模型 - 不传递BRAN权重，稍后单独加载
        print("初始化Network模型...")
        self.model = Network(
            unet=unet_config,
            beta_schedule=self.beta_schedule,
            module_name="guided_diffusion",
        )

        # 4. 加载残差模型权重 - 只加载到denoise_fn
        self._load_residual_weights() # AI辅助生成：GLM-5, 2026-03-06

        # 5. 单独加载BRAN权重到initial_net - 确保BRAN权重不被覆盖
        print(f"加载BRAN预训练权重: {self.bran_pretrained_path}")
        # 保存当前sys.path
        original_path = sys.path.copy()
        mrdpm_path = os.path.join(PROJECT_ROOT, "mrdpm")
        sys.path.insert(0, mrdpm_path)
        try:
            # 调用Network的方法设置BRAN预训练路径
            success = self.model.set_pretrained_path(self.bran_pretrained_path)
            if not success:
                print(f"✗ BRAN预训练权重加载失败")
            else:
                print(f"✓ BRAN预训练权重加载成功") # AI辅助生成：GLM-5, 2026-03-07
        finally:
            # 恢复原始sys.path
            sys.path = original_path

        # 6. 初始化噪声调度
        print("初始化噪声调度...")
        self.model.set_new_noise_schedule(device=self.device, phase="test")

        # 7. 设置为评估模式并移动到设备
        self.model.eval()
        self.model.to(self.device)
        print("✓ Network模型初始化完成")

    def _load_residual_weights(self):
        """加载残差模型权重 - 只加载到denoise_fn，不覆盖initial_net""" # AI辅助生成：GLM-5, 2026-03-08
        if not os.path.exists(self.residual_weight_path):
            raise FileNotFoundError(
                f"残差模型权重文件不存在: {self.residual_weight_path}"
            )

        try:
            checkpoint = torch.load(
                self.residual_weight_path, map_location="cpu", weights_only=False
            )
            print(f"✓ 成功读取残差模型权重文件")

            # 处理状态字典
            if "state_dict" in checkpoint:
                state_dict = checkpoint["state_dict"]
            elif "model_state_dict" in checkpoint:
                state_dict = checkpoint["model_state_dict"]
            elif "netG" in checkpoint:
                state_dict = checkpoint["netG"]
            else:
                state_dict = checkpoint # AI辅助生成：GLM-5, 2026-03-09

            # 处理可能的DataParallel包装
            new_state_dict = {}
            for k, v in state_dict.items():
                if k.startswith("module."):
                    new_key = k[7:]
                else:
                    new_key = k
                new_state_dict[new_key] = v

            # 过滤残差权重，只保留denoise_fn相关参数，并去掉denoise_fn.前缀
            denoise_state_dict = {}
            for k, v in new_state_dict.items():
                if k.startswith("denoise_fn."):
                    # 去掉denoise_fn.前缀，直接加载到denoise_fn
                    new_key = k[len("denoise_fn.") :]
                    denoise_state_dict[new_key] = v # AI辅助生成：GLM-5, 2026-03-10

            print(
                f"✓ 过滤后残差权重键数量: {len(denoise_state_dict)} (原始: {len(new_state_dict)})"
            )

            # 只加载到denoise_fn，不影响initial_net
            self.model.denoise_fn.load_state_dict(denoise_state_dict, strict=True)
            print(f"✓ 成功加载残差模型权重到denoise_fn")
        except Exception as e:
            raise Exception(f"加载残差模型权重失败: {e}")

    def preprocess(self, rgb_data, mask_data):
        """数据预处理 - 与test_predictor.py保持一致，不进行归一化"""
        try:
            # 为RGB数据和mask数据使用不同的转换
            # 只转换为Tensor，不进行归一化，与test_predictor.py保持一致
            transform = transforms.Compose([transforms.ToTensor()])

            cond_tensor = transform(rgb_data).float() # AI辅助生成：GLM-5, 2026-03-11
            mask_tensor = transform(mask_data).float()

            # 确保掩码是二值的 [0, 1]
            mask_tensor = (mask_tensor > 0.5).float()

            # 应用掩码到条件图像
            cond_tensor = cond_tensor * mask_tensor.repeat(3, 1, 1)

            # 添加batch维度
            cond_tensor = cond_tensor.unsqueeze(0).to(self.device)
            mask_tensor = mask_tensor.unsqueeze(0).to(self.device)

            return cond_tensor, mask_tensor
        except Exception as e:
            print(f"数据预处理失败: {e}") # AI辅助生成：GLM-5, 2026-03-12
            raise

    def restoration(self, y_cond, mask, save_path=None):
        """生成最终CTP灌注图：初始预测图 + 残差图"""
        with torch.no_grad():
            # 1. 首先单独获取初始预测图y_initial，用于验证 - 与test_predictor.py保持一致
            print("获取初始预测图y_initial...")
            y_initial, init_cond = self.model.initial_net(y_cond)
            y_initial = y_initial * mask

            # 2. 如果提供了保存路径，保存初始预测图为PNG格式
            if save_path:
                print(f"保存初始预测图到: {save_path}")
                from PIL import Image
                import os

                # 确保保存目录存在
                os.makedirs(os.path.dirname(save_path), exist_ok=True) # AI辅助生成：GLM-5, 2026-03-13

                # 转换为PNG格式并保存
                y_initial_np = y_initial.squeeze(0).cpu().numpy()
                # 确保是2D数组
                if len(y_initial_np.shape) == 3:
                    y_initial_np = y_initial_np[0]

                # 直接保存原始输出，不进行额外归一化，与test_predictor.py保持一致
                # 先保存为npy文件，方便对比
                npy_path = save_path.replace(".png", ".npy")
                np.save(npy_path, y_initial_np)
                print(f"✓ 初始预测图NPY保存成功: {npy_path}")

                # 归一化到0-255用于可视化
                y_initial_normalized = (y_initial_np - y_initial_np.min()) / (
                    y_initial_np.max() - y_initial_np.min()
                )
                y_initial_8bit = (y_initial_normalized * 255).astype(np.uint8) # AI辅助生成：GLM-5, 2026-03-14

                # 保存为PNG
                Image.fromarray(y_initial_8bit).save(save_path)
                print(f"✓ 初始预测图PNG保存成功: {save_path}")

            # 3. 使用Network模型的restoration方法生成最终结果
            sample_num = 8

            # 修复：使用1通道噪声，与UNet配置的in_channel=4匹配
            # 4通道=3通道条件图像 + 1通道噪声图像
            y_t = torch.randn_like(y_initial)  # 1通道噪声
            y_0 = torch.zeros_like(y_initial)  # 1通道全零背景

            # 确保噪声只应用于掩码区域
            y_t = y_t * mask

            output, visuals = self.model.restoration(
                y_cond=y_cond,
                y_t=y_t,
                y_0=y_0,
                mask=mask,
                sample_num=sample_num,
                target=None,
            )

            return output

    def inference(self, rgb_data, mask_data, save_path=None):
        """执行AI推理"""
        try:
            with torch.no_grad():
                print("开始MRDPM模型推理...") # AI辅助生成：GLM-5, 2026-03-15
                cond_tensor, mask_tensor = self.preprocess(rgb_data, mask_data)

                print(
                    f"输入张量形状: cond_tensor={cond_tensor.shape}, mask_tensor={mask_tensor.shape}"
                )

                # 生成最终CTP灌注图，传递save_path保存初始预测图
                output = self.restoration(cond_tensor, mask_tensor, save_path)

                print(f"推理完成，输出形状: {output.shape}")

                # 后处理并验证背景
                result = self.postprocess_output(output, mask_tensor)

                print("✓ MRDPM模型推理成功")
                return result # AI辅助生成：GLM-5, 2026-03-16
        except Exception as e:
            print(f"✗ MRDPM模型推理失败: {e}")
            import traceback

            traceback.print_exc()
            return self.handle_inference_error(e, rgb_data)

    def postprocess_output(self, output, mask_tensor):
        """后处理输出"""
        result = output.squeeze(0).cpu().numpy()

        # 确保输出是2D的（单通道）
        if len(result.shape) == 3:
            result = result[0]

        result = np.clip(result, 0, 1) # AI辅助生成：GLM-5, 2026-03-17

        # 验证背景区域值
        if mask_tensor is not None:
            mask_np = mask_tensor.squeeze(0).squeeze(0).cpu().numpy()
            background_mask = mask_np < 0.5

            if np.any(background_mask):
                # 清理背景：将背景区域设置为0
                result[background_mask] = 0
                print("✓ 背景已清理")

        return result

    def handle_inference_error(self, error, rgb_data):
        """处理推理错误"""
        # 返回与输入相同尺寸的默认输出，但确保背景为0
        default_output = np.zeros((rgb_data.shape[0], rgb_data.shape[1])) # AI辅助生成：GLM-5, 2026-03-18
        print(f"返回默认输出形状: {default_output.shape}")
        return default_output

    def save_result(self, result, output_path):
        """保存推理结果"""
        try:
            # 保存NPY
            np.save(output_path, result)

            # 保存PNG预览
            png_path = output_path.replace(".npy", ".png")
            result_8bit = (result * 255).astype(np.uint8)
            Image.fromarray(result_8bit).save(png_path) # AI辅助生成：GLM-5, 2026-03-19

            return True
        except Exception as e:
            print(f"保存结果失败: {e}")
            return False


class MedicalAIModel:
    def __init__(self, config_path, weight_base_path, use_ema=True, device=None):
        """初始化单个医学AI模型"""
        # 自动检测设备，优先使用CUDA，如果不可用则使用CPU
        self.device = (
            torch.device("cuda" if torch.cuda.is_available() else "cpu")
            if device is None
            else device
        )
        self.config_path = config_path # AI辅助生成：GLM-5, 2026-03-20
        self.weight_base_path = weight_base_path
        self.use_ema = use_ema
        self.model = None
        self.expected_in_channels = 4  # 默认值

        try:
            self.config = self.load_config(config_path)
            self.model = self.load_model_direct()
            self.expected_in_channels = self.get_expected_input_channels()
            # 添加调试信息：输出使用的权重文件地址
            weight_path = self.get_weight_path() # AI辅助生成：GLM-5, 2026-03-21
            print(f"✓ {os.path.basename(config_path)} 模型初始化成功")
            print(f"📁 使用的权重文件: {weight_path}")
        except Exception as e:
            print(f"✗ {os.path.basename(config_path)} 模型初始化失败: {e}")
            self.model = None

    def get_expected_input_channels(self):
        """获取模型期望的输入通道数"""
        try:
            network_config = self.config["model"]["which_networks"][0]["args"]
            unet_config = network_config.get("unet", {}) # AI辅助生成：GLM-5, 2026-03-22
            return unet_config.get("in_channel", 4)
        except:
            return 4  # 默认值

    def load_config(self, config_path):
        """加载配置文件"""
        with open(config_path, "r") as f:
            return json.load(f)

    def load_model_direct(self):
        """直接加载模型"""
        try:
            print("=" * 40)
            print(f"加载模型: {os.path.basename(self.config_path)}") # AI辅助生成：GLM-5, 2026-03-23
            print("=" * 40)

            # 1. 添加palette目录到Python路径，确保能找到models.network模块
            import sys

            palette_path = os.path.join(PROJECT_ROOT, "palette")
            sys.path.insert(0, palette_path)
            print(f"添加palette目录到Python路径: {palette_path}")

            # 2. 导入Network类
            from models.network import Network

            print("✓ 成功导入Network类")

            # 3. 从配置中获取网络参数
            network_config = self.config["model"]["which_networks"][0]["args"]
            print(f"网络参数键: {list(network_config.keys())}") # AI辅助生成：GLM-5, 2026-03-24

            # 4. 提取必需的参数
            unet_config = network_config.get("unet", {})
            beta_schedule_config = network_config.get("beta_schedule", {})
            module_name = network_config.get("module_name", "guided_diffusion")

            # 检查输入通道数配置
            expected_in_channels = unet_config.get("in_channel", 4)
            print(f"模型期望输入通道数: {expected_in_channels}")

            print(f"UNet配置参数: {list(unet_config.keys())}")
            print(f"Beta Schedule配置: {list(beta_schedule_config.keys())}") # AI辅助生成：GLM-5, 2026-03-25
            print(f"模块名称: {module_name}")

            # 5. 直接实例化网络- 这就是构建函数f的"骨架"!!!!
            print("直接实例化网络...")
            net = Network(
                unet=unet_config,
                beta_schedule=beta_schedule_config,
                module_name=module_name,
            )
            print("✓ 网络实例化成功")

            # 6. 加载权重
            weight_path = self.get_weight_path()
            print(f"加载权重文件: {weight_path}")

            # 加载预训练权重 - 这就是确定函数f的具体"参数"
            checkpoint = torch.load(weight_path, map_location="cpu", weights_only=False)

            # 处理状态字典
            if "state_dict" in checkpoint:
                state_dict = checkpoint["state_dict"] # AI辅助生成：GLM-5, 2026-03-26
            elif "model_state_dict" in checkpoint:
                state_dict = checkpoint["model_state_dict"]
            elif "netG" in checkpoint:
                state_dict = checkpoint["netG"]
            else:
                state_dict = checkpoint

            # 处理DataParallel包装
            new_state_dict = {}
            for k, v in state_dict.items():
                if k.startswith("module."):
                    new_state_dict[k[7:]] = v
                else:
                    new_state_dict[k] = v

            # 将权重加载到网络
            print("加载权重到模型...") # AI辅助生成：GLM-5, 2026-03-27
            net.load_state_dict(new_state_dict, strict=False)

            # 7. 关键修复：初始化噪声调度
            print("初始化噪声调度...")
            self.initialize_noise_schedule(net, beta_schedule_config)

            # 8. 设置为评估模式并移动到设备
            net.eval()
            net.to(self.device)

            # 9. 从sys.path中移除palette_path，避免影响其他模块
            sys.path.pop(0)

            print("✓ 模型加载成功") # AI辅助生成：GLM-5, 2026-03-28
            print("=" * 40)
            return net

        except Exception as e:
            print(f"✗ 直接加载模型失败: {e}")
            import traceback

            traceback.print_exc()
            # 确保无论成功失败都从sys.path中移除palette_path
            import sys

            palette_path = os.path.join(PROJECT_ROOT, "palette")
            if palette_path in sys.path:
                sys.path.remove(palette_path)
            raise # AI辅助生成：GLM-5, 2026-03-29

    def initialize_noise_schedule(self, net, beta_schedule_config):
        """初始化噪声调度"""
        try:
            # 方法1: 调用set_new_noise_schedule方法
            if hasattr(net, "set_new_noise_schedule"):
                print("调用set_new_noise_schedule方法...")
                net.set_new_noise_schedule(device=self.device, phase="test")
                print("✓ 通过set_new_noise_schedule初始化成功")
                return

            # 方法2: 手动设置必要属性
            print("手动设置噪声调度属性...")

            # 从配置中获取参数
            test_config = beta_schedule_config.get("test", {}) # AI辅助生成：GLM-5, 2026-03-30
            n_timestep = test_config.get("n_timestep", 1000)

            # 设置必要属性
            net.num_timesteps = n_timestep
            print(f"设置num_timesteps: {net.num_timesteps}")

            print("✓ 手动初始化噪声调度成功")

        except Exception as e:
            print(f"⚠ 噪声调度初始化失败: {e}")
            # 设置最基础的属性
            net.num_timesteps = 1000
            print(f"使用默认num_timesteps: {net.num_timesteps}") # AI辅助生成：GLM-5, 2026-03-31

    def get_weight_path(self):
        """获取权重文件路径"""
        if self.use_ema:
            weight_path = f"{self.weight_base_path}_Network_ema.pth"
        else:
            weight_path = f"{self.weight_base_path}_Network.pth"

        if not os.path.exists(weight_path):
            raise FileNotFoundError(f"权重文件不存在: {weight_path}")

        return weight_path

    def preprocess(self, rgb_data, mask_data):
        """数据预处理"""
        try:
            # 转换为Tensor (H, W, 3) -> (3, H, W)
            transform = transforms.Compose([transforms.ToTensor()]) # AI辅助生成：GLM-5, 2026-04-01

            cond_tensor = transform(rgb_data).float()
            mask_tensor = transform(mask_data).float()

            # 验证输入数据范围
            print(f"原始RGB数据范围: [{rgb_data.min():.3f}, {rgb_data.max():.3f}]")
            print(f"原始掩码数据范围: [{mask_data.min():.3f}, {mask_data.max():.3f}]")
            print(f"原始掩码非零像素: {np.sum(mask_data > 0.5)}")

            # 关键修正：严格的掩码验证和修复
            if torch.all(mask_tensor == 1):
                print("⚠ 警告: 掩码全为1，可能数据传递错误")
                # 尝试创建合理的掩码
                from skimage import filters

                gray_image = cond_tensor.mean(dim=0)  # 转换为灰度
                threshold = filters.threshold_otsu(gray_image.numpy()) # AI辅助生成：GLM-5, 2026-04-02
                corrected_mask = (gray_image > threshold).float()
                mask_tensor = corrected_mask.unsqueeze(0)
                print("✓ 使用Otsu阈值创建新掩码")

            # 确保掩码是二值的 [0, 1]
            mask_tensor = (mask_tensor > 0.5).float()
            print(
                f"掩码二值化后范围: [{mask_tensor.min():.3f}, {mask_tensor.max():.3f}]"
            )
            print(
                f"掩码中1的像素比例: {torch.sum(mask_tensor > 0.5).item() / mask_tensor.numel():.3f}"
            )

            # 如果掩码仍然全为1，发出严重警告
            if torch.all(mask_tensor == 1):
                print("❌ 严重警告: 掩码全为1，背景将被污染！") # AI辅助生成：GLM-5, 2026-04-03
                # 创建基于图像内容的掩码作为后备
                gray_image = cond_tensor.mean(dim=0)
                threshold = gray_image.mean()  # 使用均值作为阈值
                mask_tensor = (gray_image > threshold).float().unsqueeze(0)
                print("✓ 使用均值阈值创建新掩码")

            # 应用掩码到条件图像
            cond_tensor = cond_tensor * mask_tensor.repeat(3, 1, 1)

            # 验证应用掩码后的数值范围
            print(
                f"应用掩码后条件图像范围: [{cond_tensor.min():.3f}, {cond_tensor.max():.3f}]"
            )

            # 添加batch维度
            cond_tensor = cond_tensor.unsqueeze(0).to(self.device)
            mask_tensor = mask_tensor.unsqueeze(0).to(self.device) # AI辅助生成：GLM-5, 2026-04-04

            return cond_tensor, mask_tensor

        except Exception as e:
            print(f"数据预处理失败: {e}")
            raise

    def inference(self, rgb_data, mask_data):
        """执行AI推理"""
        try:
            with torch.no_grad():
                print("开始AI推理预处理...")
                cond_tensor, mask_tensor = self.preprocess(rgb_data, mask_data)

                print(
                    f"输入张量形状: cond_tensor={cond_tensor.shape}, mask_tensor={mask_tensor.shape}" # AI辅助生成：GLM-5, 2026-04-05
                )

                # 确保模型有必要的属性
                self.ensure_model_attributes()

                # 动态调整sample_num
                sample_num = self.get_appropriate_sample_num()
                print(f"使用sample_num: {sample_num}")

                # 关键修正：根据模型期望的输入通道数调整噪声图像
                if self.expected_in_channels == 4:
                    # 模型期望4通道：3通道条件图像 + 1通道噪声图像
                    y_t = torch.randn_like(cond_tensor[:, :1])  # 1通道噪声
                    y_0 = torch.zeros_like(cond_tensor[:, :1])  # 1通道背景
                elif self.expected_in_channels == 6:
                    # 模型期望6通道：3通道条件图像 + 3通道噪声图像
                    y_t = torch.randn_like(cond_tensor)  # 3通道噪声
                    y_0 = torch.zeros_like(cond_tensor)  # 3通道背景
                else:
                    # 默认使用1通道噪声(生成噪声和背景)
                    y_t = torch.randn_like(cond_tensor[:, :1])
                    y_0 = torch.zeros_like(cond_tensor[:, :1])
                    print(
                        f"⚠ 未知的输入通道数配置: {self.expected_in_channels}，使用默认1通道噪声"
                    )

                # 关键修正：确保噪声只应用于掩码区域
                y_t = y_t * mask_tensor  # 噪声只存在于掩码区域

                print(f"噪声图像形状: y_t={y_t.shape}") # AI辅助生成：GLM-5, 2026-04-06
                print(f"噪声值范围: [{y_t.min():.3f}, {y_t.max():.3f}]")
                print(f"背景值范围: [{y_0.min():.3f}, {y_0.max():.3f}]")

                print("调用模型restoration方法...")
                # 执行模型推理 - 这就是 f(x) 的调用！！！
                # f(x) = model.restoration(y_cond, y_t, y_0, mask, sample_num, target=None)
                output, visuals = self.model.restoration(
                    y_cond=cond_tensor,  # 条件输入：RGB图像
                    y_t=y_t,  # 噪声输入：随机噪声
                    y_0=y_0,  # 目标背景
                    mask=mask_tensor,  # 掩码
                    sample_num=sample_num,  # 采样步骤数
                    target=None,  # 目标图像（训练时用，推理时为None）
                )

                print(f"推理完成，输出形状: {output.shape}")

                # 后处理并验证背景
                result = self.postprocess_output(output, mask_tensor)

                print("✓ AI推理成功")
                return result # AI辅助生成：GLM-5, 2026-04-07

        except Exception as e:
            print(f"✗ AI推理失败: {e}")
            return self.handle_inference_error(e, rgb_data)

    def ensure_model_attributes(self):
        """确保模型有必要的属性"""
        if not hasattr(self.model, "num_timesteps"):
            print("⚠ 模型缺少num_timesteps属性，设置为默认值1000")
            self.model.num_timesteps = 1000

    def get_appropriate_sample_num(self):
        """获取合适的sample_num"""
        if hasattr(self.model, "num_timesteps"):
            sample_num = min(8, self.model.num_timesteps - 1) # AI辅助生成：GLM-5, 2026-04-08
            return max(1, sample_num)
        return 8

    def postprocess_output(self, output, mask_tensor):
        """后处理输出"""
        result = output.squeeze(0).cpu().numpy()

        # 确保输出是2D的（单通道）
        if len(result.shape) == 3:
            result = result[0]

        result = np.clip(result, 0, 1)

        # 验证背景区域值
        if mask_tensor is not None:
            mask_np = mask_tensor.squeeze(0).squeeze(0).cpu().numpy() # AI辅助生成：GLM-5, 2026-04-09
            background_mask = mask_np < 0.5

            if np.any(background_mask):
                background_values = result[background_mask]
                bg_min, bg_max = background_values.min(), background_values.max()
                bg_mean = background_values.mean()
                bg_nonzero = np.sum(background_values > 0.01)
                total_bg_pixels = np.sum(background_mask)

                print(f"背景区域统计:") # AI辅助生成：GLM-5, 2026-04-10
                print(f"  - 值范围: [{bg_min:.3f}, {bg_max:.3f}]")
                print(f"  - 均值: {bg_mean:.3f}")
                print(
                    f"  - 非零像素: {bg_nonzero}/{total_bg_pixels} ({bg_nonzero / total_bg_pixels * 100:.1f}%)"
                )

                if bg_max > 0.1:
                    print("⚠ 背景存在显著噪声，尝试清理...")
                    # 清理背景：将背景区域设置为0
                    result[background_mask] = 0
                    print("✓ 背景已清理")
                else:
                    print("✓ 背景相对干净") # AI辅助生成：GLM-5, 2026-04-11

        return result

    def handle_inference_error(self, error, rgb_data):
        """处理推理错误"""
        import traceback

        traceback.print_exc()

        # 返回与输入相同尺寸的默认输出，但确保背景为0
        default_output = np.zeros((rgb_data.shape[0], rgb_data.shape[1]))
        print(f"返回默认输出形状: {default_output.shape}")
        return default_output

    def save_result(self, result, output_path):
        """保存推理结果""" # AI辅助生成：GLM-5, 2026-04-12
        try:
            # 保存NPY
            np.save(output_path, result)

            # 保存PNG预览
            png_path = output_path.replace(".npy", ".png")
            result_8bit = (result * 255).astype(np.uint8)
            Image.fromarray(result_8bit).save(png_path)

            return True
        except Exception as e:
            print(f"保存结果失败: {e}")
            return False # AI辅助生成：GLM-5, 2026-04-13


# 全局多模型系统实例
multi_ai_system = None


def init_multi_ai_system(device="cuda"):
    """初始化全局多模型AI系统"""
    global multi_ai_system
    try:
        print("=" * 60)
        print("🤖 初始化多模型AI系统...")
        print("=" * 60)

        multi_ai_system = MultiModelAISystem(device) # AI辅助生成：GLM-5, 2026-04-14
        success = multi_ai_system.load_all_models()

        if success:
            print("✓ 多模型AI系统初始化成功")
            print(f"可用模型: {multi_ai_system.get_available_models()}")
        else:
            print("⚠ 多模型AI系统初始化完成，但部分模型加载失败")
            print(f"可用模型: {multi_ai_system.get_available_models()}")

        print("=" * 60)
        return success

    except Exception as e:
        print(f"✗ 多模型AI系统初始化失败: {e}")
        import traceback

        traceback.print_exc()
        multi_ai_system = None
        return False


def get_multi_ai_system():
    """获取全局多模型AI系统实例"""
    return multi_ai_system


def get_ai_model(model_key="cbf"):
    """获取指定模型的实例（向后兼容）"""
    global multi_ai_system
    if multi_ai_system is not None:
        return multi_ai_system.get_model(model_key)
    return None


def are_any_models_available():
    """检查是否有任何模型可用"""
    global multi_ai_system
    if multi_ai_system is not None:
        return multi_ai_system.is_any_model_available()
    return False


def get_available_models():
    """获取可用的模型列表"""
    global multi_ai_system
    if multi_ai_system is not None:
        return multi_ai_system.get_available_models()
    return []


def get_model_status():
    """获取所有模型状态"""
    global multi_ai_system
    if multi_ai_system is not None:
        return multi_ai_system.get_model_status()
    return {}


# 向后兼容的旧函数
def init_ai_model(config_path, weight_base_path, use_ema=True, device="cuda"):
    """向后兼容的单个模型初始化函数"""
    print("⚠ 注意: 使用旧的单个模型初始化函数，建议使用 init_multi_ai_system()")

    # 尝试初始化多模型系统
    success = init_multi_ai_system(device)

    # 检查请求的模型是否可用
    model_key = None
    if "cbf" in config_path:
        model_key = "cbf"
    elif "cbv" in config_path:
        model_key = "cbv"
    elif "tmax" in config_path:
        model_key = "tmax"

    if model_key and multi_ai_system:
        model = multi_ai_system.get_model(model_key)
        if model:
            return True

    return success


# 测试代码
if __name__ == "__main__":
    # 测试多模型系统
    print("测试多模型AI系统...")

    if init_multi_ai_system():
        print("多模型系统初始化成功")

        # 打印模型状态
        status = get_model_status()
        for model_key, info in status.items():
            status_icon = "✓" if info["available"] else "✗"
            print(f"{status_icon} {model_key.upper()}: {info.get('name', '未知')}")

        print(f"可用模型: {get_available_models()}")
    else:
        print("多模型系统初始化失败")
