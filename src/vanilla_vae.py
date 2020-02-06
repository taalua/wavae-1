import torch
import torch.nn as nn
from . import config


class ConvEncoder(nn.Module):
    """
    Multi Layer Convolutional Variational Encoder
    """
    def __init__(self):
        super().__init__()
        self.convs = nn.ModuleList([
            nn.Conv1d(config.CHANNELS[i],
                      config.CHANNELS[i+1],
                      config.KERNEL,
                      padding=config.KERNEL//2,
                      stride=config.RATIOS[i])\
            for i in range(len(config.RATIOS))
        ])
        self.bns = nn.ModuleList([
            nn.BatchNorm1d(config.CHANNELS[i])\
            for i in range(1,len(config.RATIOS))
        ])

    def forward(self, x):
        for i, conv in enumerate(self.convs):
            x = conv(x)
            if i != len(self.convs) - 1:
                x = self.bns[i](torch.relu(x))
        return x


class ConvDecoder(nn.Module):
    """
    Multi Layer Convolutional Variational Decoder
    """
    def __init__(self):
        super().__init__()
        channels = list(config.CHANNELS)
        channels[-1] //= 2
        channels[0] *= 2
        self.convs = nn.ModuleList([])
        for i in range(len(config.RATIOS))[::-1]:
            if config.RATIOS[i] != 1:
                self.convs.append(
                    nn.ConvTranspose1d(channels[i + 1],
                                       channels[i],
                                       2 * config.RATIOS[i],
                                       padding=config.RATIOS[i] // 2,
                                       stride=config.RATIOS[i]))
            else:
                self.convs.append(
                    nn.Conv1d(channels[i + 1],
                              channels[i],
                              config.KERNEL,
                              padding=config.KERNEL // 2))

        self.bns = nn.ModuleList([
            nn.BatchNorm1d(channels[i])\
            for i in range(1,len(config.RATIOS))[::-1]
        ])

    def forward(self, x):
        for i, conv in enumerate(self.convs):
            x = conv(x)
            if i != len(self.convs) - 1:
                x = self.bns[i](torch.relu(x))
        return x


class TopVAE(nn.Module):
    """
    Top Variational Auto Encoder
    """
    def __init__(self):
        super().__init__()
        self.encoder = ConvEncoder()
        self.decoder = ConvDecoder()

        skipped = 0
        for p in self.parameters():
            try:
                nn.init.xavier_normal_(p)
            except:
                skipped += 1
        print(f"Skipped {skipped} parameters during initialisation")

    def encode(self, x):
        mean, logvar = torch.split(self.encoder(x), config.CHANNELS[-1] // 2,
                                   1)
        z = torch.randn_like(mean) * torch.exp(logvar) + mean
        return z, mean, logvar

    def decode(self, z):
        rec = self.decoder(z)
        mean, logvar = torch.split(rec, config.CHANNELS[0], 1)
        mean = torch.sigmoid(mean)
        logvar = torch.clamp(logvar, min=-10, max=0)
        y = torch.randn_like(mean) * torch.exp(logvar) + mean
        return y, mean, logvar

    def forward(self, x):
        z, mean_z, logvar_z = self.encode(x)
        y, mean_y, logvar_y = self.decode(z)
        return y, mean_y, logvar_y, mean_z, logvar_z

    def loss(self, x):
        y, mean_y, logvar_y, mean_z, logvar_z = self.forward(x)

        loss_rec = logvar_y + (x - mean_y)**2 * torch.exp(-logvar_y)

        loss_reg = mean_z**2 + torch.exp(logvar_z) - logvar_z - 1

        loss_rec = torch.mean(loss_rec)
        loss_reg = torch.mean(loss_reg)

        return y, mean_y, logvar_y, mean_z, logvar_z, loss_rec, loss_reg