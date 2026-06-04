import torch
import torchreid


class ReIDModel:

    def __init__(self):

        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        self.model = torchreid.models.build_model(
            name="osnet_x0_25",
            num_classes=1000,
            pretrained=True
        )

        self.model.to(self.device)
        self.model.eval()

    def __call__(self, batch):

        batch = torch.from_numpy(batch).float().to(self.device)

        with torch.no_grad():
            features = self.model(batch)

        return features.cpu().numpy()