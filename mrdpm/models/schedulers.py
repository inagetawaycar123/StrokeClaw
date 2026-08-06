import torch
import torch.nn as nn
import torch.nn.functional as F


def LinearLR():
    return torch.optim.lr_scheduler.LinearLR()
