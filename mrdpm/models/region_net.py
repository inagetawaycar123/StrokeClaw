import torch
import torch.nn as nn
from torch.nn.utils import weight_norm
import torch.nn.functional as F
from einops import rearrange
import torch
import models.DRconv1
from dropblock import DropBlock2D


class UNetUp(nn.Module):
    def __init__(
        self,
        in_size,
        out_size,
        dropout=0.0,
        kernel_size=4,
        stride=2,
        padding=1,
        relu=True,
        outermost=False,
        innermost=False,
    ):
        super(UNetUp, self).__init__()
        if not outermost:
            layers = [
                nn.ConvTranspose2d(
                    in_size, out_size, kernel_size, stride, padding, bias=False
                ),
                nn.BatchNorm2d(out_size),
            ]
            if dropout:
                layers.append(DropBlock2D(dropout, 3))
            if relu:
                layers.append(nn.ReLU(inplace=True))
        if outermost:
            layers = [
                nn.ConvTranspose2d(
                    in_size, out_size, kernel_size, stride, padding, bias=False
                ),
                nn.Tanh(),
            ]
        self.model = nn.Sequential(*layers)
        self.outermost = outermost

    def forward(self, x, y):
        a = self.model(x)
        if self.outermost:
            return a
        a = torch.cat((a, y), 1)
        return a


class UNetDown(nn.Module):
    def __init__(
        self,
        in_size,
        out_size,
        normalize=True,
        relu=True,
        dropout=0.0,
        kernal_size=4,
        stride=2,
        padding=1,
        innermost=False,
    ):
        super(UNetDown, self).__init__()
        layers = [
            nn.Conv2d(in_size, out_size, kernal_size, stride, padding, bias=False)
        ]
        if normalize:
            layers.append(nn.BatchNorm2d(out_size))
        if dropout:
            layers.append(DropBlock2D(dropout, 3))
        if relu:
            layers.append(nn.LeakyReLU(0.2))

        if innermost:
            layers = [
                nn.Conv2d(in_size, out_size, kernal_size, stride, padding, bias=False),
                nn.ReLU(),
            ]
        self.model = nn.Sequential(*layers)

    def forward(self, x):
        return self.model(x)


class Encoderv1x(nn.Module):
    def __init__(
        self,
        in_channels=3,  # 改为3通道
        out_channels=1,
        ngf_list=[64, 128, 256, 512, 512, 512, 512, 512],
        ngf=32,
    ):
        super(Encoderv1x, self).__init__()
        region_num = 4
        self.down1 = UNetDown(in_channels * 2, int(ngf), normalize=False)
        self.down1x = models.DRconv1.DRConv2d_v8_inception(
            in_channels, in_channels, kernel_size=1, region_num=region_num
        )
        self.down2 = UNetDown(int(ngf) * 2, int(ngf * 2))
        self.down2x = models.DRconv1.DRConv2d_v8_inception(
            int(ngf), int(ngf), kernel_size=1, region_num=region_num
        )
        self.down3 = UNetDown(int(ngf * 2 * 2), int(ngf * 4))
        self.down3x = models.DRconv1.DRConv2d_v8_inception(
            int(ngf * 2), int(ngf * 2), kernel_size=1, region_num=region_num
        )
        self.down4 = UNetDown(int(ngf * 4 * 2), int(ngf * 8))
        self.down4x = models.DRconv1.DRConv2d_v8_inception(
            int(ngf * 4), int(ngf * 4), kernel_size=1, region_num=region_num
        )
        self.down5 = UNetDown(int(ngf * 8 * 2), int(ngf * 8))
        self.down5x = models.DRconv1.DRConv2d_v8_inception(
            int(ngf * 8), int(ngf * 8), kernel_size=1, region_num=region_num
        )
        self.down6 = UNetDown(int(ngf * 8 * 2), int(ngf * 8))
        self.down6x = models.DRconv1.DRConv2d_v8_inception(
            int(ngf * 8), int(ngf * 8), kernel_size=1, region_num=region_num
        )
        self.down7 = UNetDown(int(ngf * 8 * 2), int(ngf * 8))
        self.down7x = models.DRconv1.DRConv2d_v8_inception(
            int(ngf * 8), int(ngf * 8), kernel_size=1, region_num=region_num
        )
        self.down8 = UNetDown(
            int(ngf * 8 * 2), int(ngf * 8), normalize=False, innermost=True
        )
        self.down8x = models.DRconv1.DRConv2d_v8_inception(
            int(ngf * 8), int(ngf * 8), kernel_size=1, region_num=4
        )

    def forward(self, x):
        # U-Net generator with skip connections from encoder to decoder
        d1x = self.down1x(x)
        d1 = self.down1(torch.cat((x, d1x), 1))
        d2x = self.down2x(d1)
        d2 = self.down2(torch.cat((d1, d2x), 1))
        d3x = self.down3x(d2)
        d3 = self.down3(torch.cat((d2, d3x), 1))
        d4x = self.down4x(d3)
        d4 = self.down4(torch.cat((d3, d4x), 1))
        d5x = self.down5x(d4)
        d5 = self.down5(torch.cat((d4, d5x), 1))
        d6x = self.down6x(d5)
        d6 = self.down6(torch.cat((d5, d6x), 1))
        d7x = self.down7x(d6)
        d7 = self.down7(torch.cat((d6, d7x), 1))
        d8x = self.down8x(d7)
        d8 = self.down8(torch.cat((d7, d8x), 1))
        return d1, d2, d3, d4, d5, d6, d7, d8


class Unetgenerator_256(nn.Module):
    def __init__(self, in_channels=1, out_channels=1, ngf=8):
        super(Unetgenerator_256, self).__init__()
        self.encoder = Encoderv1x(ngf=ngf)

        self.up1 = UNetUp(int(ngf * 8 * (in_channels)), int(ngf * 8))
        self.up2 = UNetUp(int(ngf * 8 * (in_channels * 2)), int(ngf * 8), dropout=0.5)
        self.up3 = UNetUp(int(ngf * 8 * (in_channels * 2)), int(ngf * 8), dropout=0.5)
        self.up4 = UNetUp(int(ngf * 8 * (in_channels * 2)), int(ngf * 8), dropout=0.5)
        self.up5 = UNetUp(int(ngf * 8 * (in_channels * 2)), int(ngf * 4))
        self.up6 = UNetUp(int(ngf * 4 * (in_channels * 2)), int(ngf * 2))
        self.up7 = UNetUp(int(ngf * 2 * (in_channels * 2)), int(ngf))
        self.up8 = UNetUp(int(ngf * (in_channels * 2)), out_channels, outermost=True)

    def forward(self, x):
        hs = []
        d1, d2, d3, d4, d5, d6, d7, d8 = self.encoder(x)
        u1 = self.up1(d8, d7)
        u2 = self.up2(u1, d6)
        u3 = self.up3(u2, d5)
        u4 = self.up4(u3, d4)
        u5 = self.up5(u4, d3)
        u6 = self.up6(u5, d2)
        u7 = self.up7(u6, d1)
        u8 = self.up8(u7, x)
        hs.append(u7)
        hs.append(u6)
        hs.append(u5)
        return u8, hs
