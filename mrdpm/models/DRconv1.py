import torch.nn.functional as F
import torch.nn as nn
import torch

from torch.autograd import Variable, Function


class asign_index(torch.autograd.Function):
    @staticmethod
    def forward(ctx, kernel, guide_feature):
        ctx.save_for_backward(kernel, guide_feature)
        guide_mask = (
            torch.zeros_like(guide_feature)
            .scatter_(1, guide_feature.argmax(dim=1, keepdim=True), 1)
            .unsqueeze(2)
        )
        return torch.sum(kernel * guide_mask, dim=1)

    @staticmethod
    def backward(ctx, grad_output):
        kernel, guide_feature = ctx.saved_tensors
        guide_mask = (
            torch.zeros_like(guide_feature)
            .scatter_(1, guide_feature.argmax(dim=1, keepdim=True), 1)
            .unsqueeze(2)
        )
        grad_kernel = grad_output.clone().unsqueeze(1) * guide_mask
        grad_guide = grad_output.clone().unsqueeze(1) * kernel
        grad_guide = grad_guide.sum(dim=2)
        softmax = F.softmax(guide_feature, 1)
        grad_guide = softmax * (
            grad_guide - (softmax * grad_guide).sum(dim=1, keepdim=True)
        )
        return grad_kernel, grad_guide


def xcorr_slow(x, kernel, kwargs):
    """for loop to calculate cross correlation"""
    batch = x.size()[0]
    out = []
    for i in range(batch):
        px = x[i]
        pk = kernel[i]
        px = px.view(1, px.size()[0], px.size()[1], px.size()[2])
        pk = pk.view(-1, px.size()[1], pk.size()[1], pk.size()[2])
        po = F.conv2d(px, pk, padding=0, **kwargs)
        out.append(po)
    out = torch.cat(out, 0)
    return out


def xcorr_fast(x, kernel, kwargs):
    """group conv2d to calculate cross correlation"""
    batch = kernel.size()[0]
    pk = kernel.view(-1, x.size()[1], kernel.size()[2], kernel.size()[3])
    px = x.view(1, -1, x.size()[2], x.size()[3])
    po = F.conv2d(px, pk, padding=0, **kwargs, groups=batch)
    po = po.view(batch, -1, po.size()[2], po.size()[3])
    return po


class Corr(Function):
    @staticmethod
    def symbolic(g, x, kernel, groups):
        return g.op("Corr", x, kernel, groups_i=groups)

    @staticmethod
    def forward(self, x, kernel, groups, kwargs):
        """group conv2d to calculate cross correlation"""
        batch = x.size(0)
        channel = x.size(1)
        x = x.view(1, -1, x.size(2), x.size(3))
        kernel = kernel.view(-1, channel // groups, kernel.size(2), kernel.size(3))
        out = F.conv2d(x, kernel, padding=0, **kwargs, groups=groups * batch)
        out = out.view(batch, -1, out.size(2), out.size(3))
        return out


class Correlation(nn.Module):
    use_slow = True

    def __init__(self, use_slow=None):
        super(Correlation, self).__init__()
        if use_slow is not None:
            self.use_slow = use_slow
        else:
            self.use_slow = Correlation.use_slow

    def extra_repr(self):
        if self.use_slow:
            return "xcorr_slow"
        return "xcorr_fast"

    def forward(self, x, kernel, **kwargs):
        if self.training:
            if self.use_slow:
                return xcorr_slow(x, kernel, kwargs)
            else:
                return xcorr_fast(x, kernel, kwargs)
        else:
            return Corr.apply(x, kernel, 1, kwargs)


class DRConv2d_v8_inception(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, region_num=8, **kwargs):
        super(DRConv2d_v8_inception, self).__init__()
        self.region_num = region_num
        self.conv_kernel_1 = nn.Sequential(
            nn.AdaptiveAvgPool2d((kernel_size, kernel_size)),
            nn.Conv2d(in_channels, region_num * region_num, kernel_size=1),
            nn.SiLU(),
            nn.Conv2d(region_num * region_num, region_num * region_num, kernel_size=1),
            nn.SiLU(),
            nn.Conv2d(
                region_num * region_num,
                region_num * in_channels * out_channels,
                kernel_size=1,
                groups=region_num,
            ),
        )

        self.conv_kernel_2 = nn.Sequential(
            nn.AdaptiveAvgPool2d((kernel_size, kernel_size)),
            nn.Conv2d(in_channels, region_num * region_num, kernel_size=1),
            nn.Sigmoid(),
            nn.Conv2d(
                region_num * region_num,
                region_num * in_channels * out_channels,
                kernel_size=1,
                groups=region_num,
            ),
        )

        self.conv_guide = nn.Conv2d(
            in_channels, region_num, kernel_size=kernel_size, padding=0, **kwargs
        )

        self.corr = Correlation(use_slow=False)
        self.kwargs = kwargs
        self.asign_index_1 = asign_index.apply
        self.asign_index_2 = asign_index.apply

    def forward(self, input):
        kernel_1 = self.conv_kernel_1(input)
        kernel_1 = kernel_1.view(
            kernel_1.size(0), -1, kernel_1.size(2), kernel_1.size(3)
        )
        output_1 = self.corr(input, kernel_1, **self.kwargs)
        output_1 = output_1.view(
            output_1.size(0), self.region_num, -1, output_1.size(2), output_1.size(3)
        )

        kernel_2 = self.conv_kernel_2(input)
        kernel_2 = kernel_2.view(
            kernel_2.size(0), -1, kernel_2.size(2), kernel_2.size(3)
        )
        output_2 = self.corr(input, kernel_2, **self.kwargs)
        output_2 = output_2.view(
            output_2.size(0), self.region_num, -1, output_2.size(2), output_2.size(3)
        )

        guide_feature = self.conv_guide(input)
        output_1 = self.asign_index_1(output_1, guide_feature)
        output_2 = self.asign_index_2(output_2, guide_feature)
        return output_1 + output_2
