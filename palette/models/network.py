import math
import torch
from inspect import isfunction
from functools import partial
import numpy as np
from tqdm import tqdm
from core.base_network import BaseNetwork
import torch.nn.functional as F


class Network(BaseNetwork):
    def __init__(self, unet, beta_schedule, module_name="sr3", **kwargs):
        super(Network, self).__init__(**kwargs)
        # if module_name == 'sr3':
        #     from .sr3_modules.unet import UNet
        if module_name == "guided_diffusion":
            from .guided_diffusion_modules.unet import UNet
        # elif module_name == 'medsegdiff':
        #     from .medsegdiff_modules.med_seg_diff_pytorch import UNet
        # elif module_name == 'cd':
        #     from .my_diffusion_v0.unet import UNet
        # elif module_name == 'multiout':
        #     from .multiout_diffusion_modules.unet import UNet

        # 显示模型结构
        self.denoise_fn = UNet(**unet)

        self.beta_schedule = beta_schedule
        self.module_name = module_name
        # ...

    def set_loss(self, loss_fn):
        self.loss_fn = loss_fn

    def set_new_noise_schedule(self, device=torch.device("cuda"), phase="train"):
        to_torch = partial(torch.tensor, dtype=torch.float32, device=device)
        betas = make_beta_schedule(**self.beta_schedule[phase])
        betas = (
            betas.detach().cpu().numpy() if isinstance(betas, torch.Tensor) else betas
        )
        alphas = 1.0 - betas

        (timesteps,) = betas.shape
        self.num_timesteps = int(timesteps)

        gammas = np.cumprod(alphas, axis=0)  # 等同于alphas_bar
        gammas_prev = np.append(
            1.0, gammas[:-1]
        )  # 有可能和下面这个东西相同相当于'alphas_bar_prev_whole'，但是下面一行表示只在左边填1，这一行截掉了最后一个数，不知道会不会有影响！！！！
        self.gammas_prev = to_torch(np.append(1.0, gammas))  # ddim加装的
        # self.register_buffer('alphas_bar_prev_whole', F.pad(gammas , [1, 0], value=1))# 用于ddim
        # calculations for diffusion q(x_t | x_{t-1}) and others
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

    def p_mean_variance(self, y_t, t, clip_denoised: bool, y_cond=None):
        noise_level = extract(
            self.gammas, t, x_shape=(1, 1)
        ).to(
            y_t.device
        )  # 原来的程序可能就有问题，从这一段程序来看，extract的是gammas正位，但是我训练的时候用的是-1位
        if self.module_name == "medsegdiff":
            y_0_hat = self.predict_start_from_noise(
                y_t, t=t, noise=self.denoise_fn(torch.cat([y_cond, y_t], dim=1), t)
            )
        else:
            y_0_hat = self.predict_start_from_noise(
                y_t,
                t=t,
                noise=self.denoise_fn(torch.cat([y_cond, y_t], dim=1), noise_level),
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
    def p_sample(self, y_t, t, clip_denoised=True, y_cond=None):
        model_mean, model_log_variance = self.p_mean_variance(
            y_t=y_t, t=t, clip_denoised=clip_denoised, y_cond=y_cond
        )
        noise = torch.randn_like(y_t) if any(t > 0) else torch.zeros_like(y_t)
        return model_mean + noise * (0.5 * model_log_variance).exp()

    @torch.no_grad()
    def restoration(
        self, y_cond, y_t=None, y_0=None, mask=None, sample_num=8, target=None
    ):
        b, *_ = y_cond.shape

        assert self.num_timesteps > sample_num, (
            "num_timesteps must greater than sample_num"
        )
        sample_inter = self.num_timesteps // sample_num
        if target is not None:
            # y_t = default(y_t, lambda: torch.randn_like(target))
            y_t = torch.randn_like(target) * mask + y_0 * (1.0 - mask)
        else:
            y_t = default(
                y_t, lambda: torch.randn_like(y_cond)
            )  # 这一段是原程序，它根据输入的cond ch数量决定val时的噪声图通道数量修改为
        # universal_show_img(y_t[0,0,:,:], 'gray')
        ret_arr = y_t
        for i in tqdm(
            reversed(range(0, self.num_timesteps)),
            desc="sampling loop time step",
            total=self.num_timesteps,
        ):
            t = torch.full((b,), i, device=y_cond.device, dtype=torch.long)
            y_t = self.p_sample(y_t, t, y_cond=y_cond)
            if mask is not None:
                y_t = (
                    y_0 * (1.0 - mask) + mask * y_t
                )  # 暂时没搞懂y0是什么，在这个yt只有在inpainting和uncroping存在时用到，（我的任务更接近collourization）
            if i % sample_inter == 0:
                ret_arr = torch.cat([ret_arr, y_t], dim=0)
        return y_t, ret_arr

    @torch.no_grad()
    def predict_start_from_noise_ddim(self, y_t, t, noise):
        return (
            extract(self.sqrt_recip_gammas, t, y_t.shape) * y_t
            - extract(self.sqrt_recipm1_gammas, t, y_t.shape) * noise
        ), noise

    @torch.no_grad()
    def p_mean_variance_ddim(self, y_t, t, clip_denoised: bool, y_cond=None):
        noise_level = extract(self.gammas, t, x_shape=(1, 1)).to(y_t.device)
        if self.module_name == "medsegdiff":
            y_0_hat, noise = self.predict_start_from_noise_ddim(
                y_t, t=t, noise=self.denoise_fn(torch.cat([y_cond, y_t], dim=1), t)
            )
        else:
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
            # y_t = default(y_t, lambda: torch.randn_like(target))
            y_t = torch.randn_like(target) * mask + y_0 * (1.0 - mask)
        else:
            y_t = default(
                y_t, lambda: torch.randn_like(y_cond)
            )  # 这一段是原程序，它根据输入的cond ch数量决定val时的噪声图通道数量修改为
        # universal_show_img(y_t[0,0,:,:], 'gray')
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
            alpha_cumprod_t = extract(self.gammas_prev, t, y_t.shape)  # 正确
            alpha_cumprod_t_prev = extract(self.gammas_prev, prev_t, y_t.shape)  # 正确
            self.ddim_eta = 0  #
            # 根据训练好的ddpm算eps
            y_0_pred, noise = self.p_mean_variance_ddim(
                y_t=y_t, t=t_1, clip_denoised=True, y_cond=y_cond
            )
            # 计算sigma,用于第三项
            sigma_t = self.ddim_eta * torch.sqrt(
                (1 - alpha_cumprod_t_prev)
                / (1 - alpha_cumprod_t)
                * (1 - alpha_cumprod_t / alpha_cumprod_t_prev)
            )

            # 用于第二项
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

    def forward(self, y_0, y_cond=None, mask=None, noise=None):
        # sampling from p(gammas)
        b, *_ = y_0.shape
        t = torch.randint(1, self.num_timesteps, (b,), device=y_0.device).long()  # 1-99
        gamma_t1 = extract(
            self.gammas, t, x_shape=(1, 1)
        )  # 去除鲁棒性，从原来的restoration程序来看，应该从t采样gamma不是t-1，应改成t，对之前两个模型都有影响，因为ynoise采样基于这个
        sqrt_gamma_t2 = extract(self.gammas, t, x_shape=(1, 1))
        # sample_gammas = (sqrt_gamma_t2-gamma_t1) * torch.rand((b, 1), device=y_0.device) + gamma_t1 # 用了一个随机变量，可能是为了增强鲁棒性
        sample_gammas = gamma_t1
        sample_gammas = sample_gammas.view(b, -1)

        noise = default(noise, lambda: torch.randn_like(y_0))
        y_noisy = self.q_sample(
            y_0=y_0, sample_gammas=sample_gammas.view(-1, 1, 1, 1), noise=noise
        )
        # universal_show_img(y_noisy[0,0,:,:], 'gray')
        # universal_show_img(y_0[0,0,:,:], 'gray')
        if mask is not None:
            if self.module_name == "medsegdiff":
                noise_hat = self.denoise_fn(
                    torch.cat([y_cond, y_noisy * mask + (1.0 - mask) * y_0], dim=1), t
                )
            else:
                noise_hat = self.denoise_fn(
                    torch.cat([y_cond, y_noisy * mask + (1.0 - mask) * y_0], dim=1),
                    sample_gammas,
                )
            loss = self.loss_fn(mask * noise, mask * noise_hat)
        else:
            if self.module_name == "medsegdiff":
                noise_hat = self.denoise_fn(torch.cat([y_cond, y_noisy], dim=1), t)
            noise_hat = self.denoise_fn(
                torch.cat([y_cond, y_noisy], dim=1), sample_gammas
            )  # 逆向过程in_ch=5u因为我的输入是4+1，但是本程序的前向过程写的有问题，其根据cond的channel数量设置噪声，所以需要修改
            loss = self.loss_fn(noise, noise_hat)
        return loss


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
    """
    sigmoid schedule
    proposed in https://arxiv.org/abs/2212.11972 - Figure 8
    better for images > 64x64, when used during training
    """
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
    elif schedule == "jsd":  # 1/T, 1/(T-1), 1/(T-2), ..., 1
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
