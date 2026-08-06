import math
import torch
from inspect import isfunction
from functools import partial
import numpy as np
from tqdm import tqdm
from core.base_network import BaseNetwork
import torch.nn.functional as F

# from torchviz import make_dot
from .networks_unet256 import define_G

# import pydot_ng
import os


class Network(BaseNetwork):
    def __init__(self, unet, beta_schedule, module_name="sr3", **kwargs):
        # 先从kwargs中提取bran_pretrained_path，避免传递给父类
        bran_pretrained_path = kwargs.pop("bran_pretrained_path", None)

        # 调用父类初始化，此时kwargs中已不包含bran_pretrained_path
        super(Network, self).__init__(**kwargs)

        from .guided_diffusion_modules.unet import UNet

        # 显示模型结构
        self.denoise_fn = UNet(**unet)
        self.initial_net = define_G(
            3, 1, 32, use_dropout=True, init_type="kaiming", gpu_ids=[]
        )  # 与终端脚本保持一致的参数
        self.beta_schedule = beta_schedule
        self.module_name = module_name

        # 初始化预训练路径
        self.bran_pretrained_path = None

        # 新增：统一权重加载逻辑
        if bran_pretrained_path:
            self.set_pretrained_path(bran_pretrained_path)
            print(f"📋 初始化时接收到的预训练路径: {bran_pretrained_path}")

    def set_pretrained_path(self, path):
        """设置预训练权重路径并立即加载权重"""
        if not path:
            print("⚠️ 提供的预训练路径为空")
            return False

        self.bran_pretrained_path = path
        print(f"📁 设置预训练权重路径: {path}")

        # 立即尝试加载权重
        return self._load_pretrained_weights(path)

    def _load_pretrained_weights(self, path):
        """内部方法：实际加载预训练权重 - 与test_predictor.py保持一致"""
        if not path or not os.path.exists(path):
            print(f"❌ 预训练权重文件不存在: {path}")
            return False

        try:
            # 加载预训练权重
            checkpoint = torch.load(path, map_location="cpu")
            print(f"✅ 成功读取权重文件，包含键: {list(checkpoint.keys())}")

            # 处理检查点或纯权重文件，与test_predictor.py保持一致
            if "model_state_dict" in checkpoint:
                # 加载完整检查点
                state_dict = checkpoint["model_state_dict"]
                print(f"📋 从检查点加载权重，epoch: {checkpoint.get('epoch', '未知')}")
            elif "state_dict" in checkpoint:
                # 另一种检查点格式
                state_dict = checkpoint["state_dict"]
                print(f"📋 从state_dict键加载权重")
            else:
                # 加载纯权重文件
                state_dict = checkpoint
                print("📋 直接加载纯权重文件")

            # 处理可能的DataParallel包装
            if all(key.startswith("module.") for key in state_dict.keys()):
                print("🔧 检测到DataParallel包装，移除'module.'前缀")
                state_dict = {k[7:]: v for k, v in state_dict.items()}

            # 检查网络结构与权重兼容性
            initial_net_state = self.initial_net.state_dict()
            missing_keys = []
            unexpected_keys = []

            for key in state_dict.keys():
                if key not in initial_net_state:
                    unexpected_keys.append(key)

            for key in initial_net_state.keys():
                if key not in state_dict:
                    missing_keys.append(key)

            if missing_keys:
                print(f"⚠️ 权重文件中缺少以下键: {missing_keys[:5]}...")  # 只显示前5个
            if unexpected_keys:
                print(f"⚠️ 权重文件中有意外键: {unexpected_keys[:5]}...")

            # 加载到初始网络
            self.initial_net.load_state_dict(state_dict, strict=False)
            print(f"✅ 成功加载BRAN预训练权重到initial_net")

            # 验证权重加载
            self._verify_weight_loading()

            # 可选：冻结BRAN网络参数
            # self._freeze_pretrained_weights()

            return True

        except Exception as e:
            print(f"❌ 加载BRAN预训练权重失败: {e}")
            import traceback

            print(f"错误堆栈: {traceback.format_exc()}")
            return False

    def _verify_weight_loading(self):
        """验证权重是否成功加载"""
        print("🔍 开始验证权重加载情况...")

        # 检查参数统计
        total_params = sum(p.numel() for p in self.initial_net.parameters())
        trained_params = sum(
            p.numel() for p in self.initial_net.parameters() if p.requires_grad
        )

        print(f"📊 BRAN网络参数统计:")
        print(f"   总参数数: {total_params:,}")
        print(f"   可训练参数: {trained_params:,}")
        print(f"   冻结参数: {total_params - trained_params:,}")

        # 前向传播测试
        try:
            with torch.no_grad():
                # 创建测试输入（匹配实际输入尺寸）
                test_input = torch.randn(1, 3, 256, 256)  # 输入通道修改为3通道
                output = self.initial_net(test_input)

                # 处理网络可能返回元组的情况
                if isinstance(output, tuple):
                    print(f"⚠️ 网络返回元组，包含 {len(output)} 个输出")
                    # 取第一个元素作为主输出进行验证
                    output = output[0]
                    print(f"✅ 使用第一个输出进行验证，形状: {output.shape}")

                print(f"✅ BRAN网络前向传播测试通过")
                print(f"   输入形状: {test_input.shape}")
                print(f"   输出形状: {output.shape}")
                print(
                    f"   输出范围: [{output.min().item():.3f}, {output.max().item():.3f}]"
                )

                # 检查输出是否合理
                if torch.isnan(output).any() or torch.isinf(output).any():
                    print("❌ 输出包含NaN或Inf值")
                else:
                    print("✅ 输出值正常")

        except Exception as e:
            print(f"❌ BRAN网络前向传播失败: {e}")

    def _freeze_pretrained_weights(self):
        """冻结预训练权重"""
        print("🔒 冻结BRAN网络参数...")
        for name, param in self.initial_net.named_parameters():
            param.requires_grad = False
        print("✅ BRAN网络参数已冻结")

    def set_loss(self, loss_fn):
        self.loss_fn = loss_fn
        self.loss_initial = torch.nn.L1Loss()

    def set_new_noise_schedule(self, device=torch.device("cuda"), phase="train"):
        to_torch = partial(torch.tensor, dtype=torch.float32, device=device)
        betas = make_beta_schedule(**self.beta_schedule[phase])
        betas = (
            betas.detach().cpu().numpy() if isinstance(betas, torch.Tensor) else betas
        )
        alphas = 1.0 - betas

        (timesteps,) = betas.shape
        self.num_timesteps = int(timesteps)

        gammas = np.cumprod(alphas, axis=0)
        gammas_prev = np.append(1.0, gammas[:-1])
        self.gammas_prev = to_torch(np.append(1.0, gammas))
        self.register_buffer("gammas", to_torch(gammas))
        self.register_buffer("sqrt_recip_gammas", to_torch(np.sqrt(1.0 / gammas)))
        self.register_buffer("sqrt_recipm1_gammas", to_torch(np.sqrt(1.0 / gammas - 1)))

        # calculations for posterior q(x_{t-1} | x_t, x_0)
        posterior_variance = betas * (1.0 - gammas_prev) / (1.0 - gammas)
        # below: log calculation clipped because the posterior variance is 0 at the beginning of the diffusion chain
        self.register_buffer(
            "posterior_log_variance_clipped",
            to_torch(np.log(np.maximum(posterior_variance, 1e-20))),
        )
        self.register_buffer(
            "posterior_mean_coef1",
            to_torch(betas * np.sqrt(gammas_prev) / (1.0 - gammas)),
        )
        self.register_buffer(
            "posterior_mean_coef2",
            to_torch((1.0 - gammas_prev) * np.sqrt(alphas) / (1.0 - gammas)),
        )

    def predict_start_from_noise(self, y_t, t, noise):
        return (
            extract(self.sqrt_recip_gammas, t, y_t.shape) * y_t
            - extract(self.sqrt_recipm1_gammas, t, y_t.shape) * noise
        )

    def q_posterior(self, y_0_hat, y_t, t):
        posterior_mean = (
            extract(self.posterior_mean_coef1, t, y_t.shape) * y_0_hat
            + extract(self.posterior_mean_coef2, t, y_t.shape) * y_t
        )
        posterior_log_variance_clipped = extract(
            self.posterior_log_variance_clipped, t, y_t.shape
        )
        return posterior_mean, posterior_log_variance_clipped

    def p_mean_variance(self, y_t, t, clip_denoised: bool, y_cond=None, init_cond=None):
        noise_level = extract(self.gammas, t, x_shape=(1, 1)).to(y_t.device)

        y_0_hat = self.predict_start_from_noise(
            y_t,
            t=t,
            noise=self.denoise_fn(
                torch.cat([y_cond, y_t], dim=1), noise_level, init_cond
            ),
        )

        if clip_denoised:
            y_0_hat.clamp_(-1.0, 1.0)

        model_mean, posterior_log_variance = self.q_posterior(
            y_0_hat=y_0_hat, y_t=y_t, t=t
        )
        return model_mean, posterior_log_variance

    def q_sample(self, y_0, sample_gammas, noise=None):
        noise = default(noise, lambda: torch.randn_like(y_0))
        return sample_gammas.sqrt() * y_0 + (1 - sample_gammas).sqrt() * noise

    @torch.no_grad()
    def p_sample(self, y_t, t, init_cond, clip_denoised=True, y_cond=None):
        model_mean, model_log_variance = self.p_mean_variance(
            y_t=y_t,
            t=t,
            clip_denoised=clip_denoised,
            y_cond=y_cond,
            init_cond=init_cond,
        )
        noise = torch.randn_like(y_t) if any(t > 0) else torch.zeros_like(y_t)
        return model_mean + noise * (0.5 * model_log_variance).exp()

    @torch.no_grad()
    def restoration(
        self, y_cond, y_t=None, y_0=None, mask=None, sample_num=8, target=None
    ):
        b, *_ = y_cond.shape
        y_initial, init_cond = self.initial_net(y_cond)
        y_initial = y_initial * mask
        assert self.num_timesteps > sample_num, (
            "num_timesteps must greater than sample_num"
        )
        sample_inter = self.num_timesteps // sample_num
        if target is not None:
            y_t = torch.randn_like(target) * mask + y_0 * (1.0 - mask)
        else:
            y_t = default(y_t, lambda: torch.randn_like(y_cond))
        ret_arr = y_t
        for i in tqdm(
            reversed(range(0, self.num_timesteps)),
            desc="sampling loop time step",
            total=self.num_timesteps,
        ):
            t = torch.full((b,), i, device=y_cond.device, dtype=torch.long)
            y_t = self.p_sample(y_t, t, y_cond=y_cond, init_cond=init_cond)
            if mask is not None:
                y_t = y_0 * (1.0 - mask) + mask * y_t
            if i % sample_inter == 0:
                ret_arr = torch.cat([ret_arr, y_t], dim=0)

        return y_t + y_initial, ret_arr

    @torch.no_grad()
    def predict_start_from_noise_ddim(self, y_t, t, noise):
        return (
            extract(self.sqrt_recip_gammas, t, y_t.shape) * y_t
            - extract(self.sqrt_recipm1_gammas, t, y_t.shape) * noise
        ), noise

    @torch.no_grad()
    def p_mean_variance_ddim(self, y_t, t, clip_denoised: bool, y_cond=None):
        noise_level = extract(self.gammas, t, x_shape=(1, 1)).to(y_t.device)

        y_0_hat, noise = self.predict_start_from_noise_ddim(
            y_t,
            t=t,
            noise=self.denoise_fn(torch.cat([y_cond, y_t], dim=1), noise_level),
        )

        if clip_denoised:
            y_0_hat.clamp_(-1.0, 1.0)

        return y_0_hat, noise

    @torch.no_grad()
    def restoration_ddim(
        self,
        y_cond,
        y_t=None,
        y_0=None,
        mask=None,
        sample_num=5,
        target=None,
        sample_steps=20,
    ):
        b, *_ = y_cond.shape

        assert self.num_timesteps > sample_num, (
            "num_timesteps must greater than sample_num"
        )
        sample_inter = self.num_timesteps // sample_num
        if target is not None:
            y_t = torch.randn_like(target) * mask + y_0 * (1.0 - mask)
        else:
            y_t = default(y_t, lambda: torch.randn_like(y_cond))

        ret_arr = y_t
        for i, j in tqdm(
            zip(
                reversed(
                    list(
                        torch.arange(sample_steps, self.num_timesteps + 1, sample_steps)
                    )
                ),
                reversed(
                    list(
                        torch.arange(sample_steps, self.num_timesteps + 1, sample_steps)
                        - sample_steps
                    )
                ),
            ),
            desc="Inference",
        ):
            t = torch.full((b,), i, device=y_cond.device, dtype=torch.long)
            prev_t = torch.full((b,), j, device=y_cond.device, dtype=torch.long)
            t_1 = torch.full((b,), i - 1, device=y_cond.device, dtype=torch.long)
            alpha_cumprod_t = extract(self.gammas_prev, t, y_t.shape)
            alpha_cumprod_t_prev = extract(self.gammas_prev, prev_t, y_t.shape)
            self.ddim_eta = 0  #

            y_0_pred, noise = self.p_mean_variance_ddim(
                y_t=y_t, t=t_1, clip_denoised=True, y_cond=y_cond
            )

            sigma_t = self.ddim_eta * torch.sqrt(
                (1 - alpha_cumprod_t_prev)
                / (1 - alpha_cumprod_t)
                * (1 - alpha_cumprod_t / alpha_cumprod_t_prev)
            )

            pred_dir_xt = torch.sqrt(1 - alpha_cumprod_t_prev - sigma_t**2) * noise

            y_prev = (
                torch.sqrt(alpha_cumprod_t_prev) * y_0_pred
                + pred_dir_xt
                + sigma_t**2 * torch.randn_like(y_t)
            )
            y_t = y_prev
            if mask is not None:
                y_t = y_0 * (1.0 - mask) + mask * y_t
            if i % sample_inter == 0:
                ret_arr = torch.cat([ret_arr, y_t], dim=0)
        return y_t, ret_arr

    """ def forward(self, y_0, y_cond=None, mask=None, noise=None):
        # sampling from p(gammas)
        b, *_ = y_0.shape
        t = torch.randint(1, self.num_timesteps, (b,), device=y_0.device).long()  # 1-99
        gamma_t1 = extract(self.gammas, t, x_shape=(1, 1))
        sqrt_gamma_t2 = extract(self.gammas, t, x_shape=(1, 1))
        sample_gammas = gamma_t1
        sample_gammas = sample_gammas.view(b, -1)

        y_initial, init_cond = self.initial_net(y_cond)
        y_initial = y_initial * mask
        y_res = (y_0 - y_initial) * mask

        noise = default(noise, lambda: torch.randn_like(y_0))
        y_noisy = self.q_sample(
            y_0=y_res, sample_gammas=sample_gammas.view(-1, 1, 1, 1), noise=noise)
        if mask is not None:
            noise_hat = self.denoise_fn(torch.cat([y_cond, y_noisy * mask + (1. - mask) * y_0], dim=1), sample_gammas, init_cond)
            loss = self.loss_fn(mask * noise, mask * noise_hat) + self.loss_initial(y_0, y_initial) * 0.1
        else:
            noise_hat = self.denoise_fn(torch.cat([y_cond, y_noisy], dim=1), sample_gammas, init_cond)
            loss = self.loss_fn(noise, noise_hat) + self.loss_initial(y_0, y_initial) * 0.1
        return loss """

    def forward(self, y_0, y_cond=None, mask=None, noise=None):
        # sampling from p(gammas)
        b, *_ = y_0.shape
        t = torch.randint(1, self.num_timesteps, (b,), device=y_0.device).long()  # 1-99
        gamma_t1 = extract(self.gammas, t, x_shape=(1, 1))
        sqrt_gamma_t2 = extract(self.gammas, t, x_shape=(1, 1))
        sample_gammas = gamma_t1
        sample_gammas = sample_gammas.view(b, -1)

        # 处理 initial_net 可能返回元组的情况
        initial_output = self.initial_net(y_cond)
        if isinstance(initial_output, tuple):
            y_initial, init_cond = (
                initial_output[0],
                initial_output[1],
            )  # 根据实际输出调整
            # print(f"⚠️ initial_net返回元组，使用前两个元素")
        else:
            y_initial, init_cond = initial_output, None  # 默认处理
            # print(f"⚠️ initial_net返回单张量，init_cond设为None")

        y_initial = y_initial * mask
        y_res = (y_0 - y_initial) * mask

        noise = default(noise, lambda: torch.randn_like(y_0))
        y_noisy = self.q_sample(
            y_0=y_res, sample_gammas=sample_gammas.view(-1, 1, 1, 1), noise=noise
        )
        if mask is not None:
            noise_hat = self.denoise_fn(
                torch.cat([y_cond, y_noisy * mask + (1.0 - mask) * y_0], dim=1),
                sample_gammas,
                init_cond,
            )
            loss = (
                self.loss_fn(mask * noise, mask * noise_hat)
                + self.loss_initial(y_0, y_initial) * 0.1
            )
        else:
            noise_hat = self.denoise_fn(
                torch.cat([y_cond, y_noisy], dim=1), sample_gammas, init_cond
            )
            print(f"⚠️ init_cond为None，可能影响denoise_fn性能")
            loss = (
                self.loss_fn(noise, noise_hat) + self.loss_initial(y_0, y_initial) * 0.1
            )
        return loss

    # 保留原有验证方法
    def verify_pretrained_weights(self):
        """验证预训练权重加载情况（兼容旧版本）"""
        self._verify_weight_loading()


# gaussian diffusion trainer class
def exists(x):
    return x is not None


def default(val, d):
    if exists(val):
        return val
    return d() if isfunction(d) else d


def extract(a, t, x_shape=(1, 1, 1, 1)):
    b, *_ = t.shape
    out = a.gather(-1, t)
    return out.reshape(b, *((1,) * (len(x_shape) - 1)))


# beta_schedule function
def _warmup_beta(linear_start, linear_end, n_timestep, warmup_frac):
    betas = linear_end * np.ones(n_timestep, dtype=np.float64)
    warmup_time = int(n_timestep * warmup_frac)
    betas[:warmup_time] = np.linspace(
        linear_start, linear_end, warmup_time, dtype=np.float64
    )
    return betas


def sigmoid_beta_schedule(timesteps, start=-3, end=3, tau=1, clamp_min=1e-5):
    steps = timesteps + 1
    t = torch.linspace(0, timesteps, steps, dtype=torch.float64) / timesteps
    v_start = torch.tensor(start / tau).sigmoid()
    v_end = torch.tensor(end / tau).sigmoid()
    alphas_cumprod = (-((t * (end - start) + start) / tau).sigmoid() + v_end) / (
        v_end - v_start
    )
    alphas_cumprod = alphas_cumprod / alphas_cumprod[0]
    betas = 1 - (alphas_cumprod[1:] / alphas_cumprod[:-1])
    return torch.clip(betas, 0, 0.999)


def make_beta_schedule(
    schedule, n_timestep, linear_start=1e-6, linear_end=1e-2, cosine_s=8e-3
):
    if schedule == "quad":
        betas = (
            np.linspace(
                linear_start**0.5, linear_end**0.5, n_timestep, dtype=np.float64
            )
            ** 2
        )
    elif schedule == "linear":
        betas = np.linspace(linear_start, linear_end, n_timestep, dtype=np.float64)
    elif schedule == "warmup10":
        betas = _warmup_beta(linear_start, linear_end, n_timestep, 0.1)
    elif schedule == "warmup50":
        betas = _warmup_beta(linear_start, linear_end, n_timestep, 0.5)
    elif schedule == "const":
        betas = linear_end * np.ones(n_timestep, dtype=np.float64)
    elif schedule == "jsd":
        betas = 1.0 / np.linspace(n_timestep, 1, n_timestep, dtype=np.float64)
    elif schedule == "cosine":
        timesteps = (
            torch.arange(n_timestep + 1, dtype=torch.float64) / n_timestep + cosine_s
        )
        alphas = timesteps / (1 + cosine_s) * math.pi / 2
        alphas = torch.cos(alphas).pow(2)
        alphas = alphas / alphas[0]
        betas = 1 - alphas[1:] / alphas[:-1]
        betas = betas.clamp(max=0.999)
    elif schedule == "sigmoid":
        betas = sigmoid_beta_schedule(n_timestep)
    else:
        raise NotImplementedError(schedule)
    return betas
