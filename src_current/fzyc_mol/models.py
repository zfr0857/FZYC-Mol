from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F
from torch_geometric.nn import GINEConv, TransformerConv, global_max_pool, global_mean_pool


class MLP(nn.Module):
    def __init__(
        self,
        in_dim: int,
        hidden_dim: int,
        out_dim: int,
        layers: int = 2,
        dropout: float = 0.15,
    ) -> None:
        super().__init__()
        modules: list[nn.Module] = []
        dim = in_dim
        for _ in range(max(1, layers - 1)):
            modules.extend(
                [
                    nn.Linear(dim, hidden_dim),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                ]
            )
            dim = hidden_dim
        modules.append(nn.Linear(dim, out_dim))
        self.net = nn.Sequential(*modules)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class GINEGraphEncoder(nn.Module):
    def __init__(
        self,
        atom_dim: int,
        bond_dim: int,
        hidden_dim: int,
        layers: int,
        dropout: float = 0.15,
    ) -> None:
        super().__init__()
        self.atom_in = nn.Linear(atom_dim, hidden_dim)
        self.edge_in = nn.Linear(bond_dim, hidden_dim)
        self.convs = nn.ModuleList()
        self.norms = nn.ModuleList()
        self.dropout = dropout
        for _ in range(layers):
            mlp = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim),
            )
            self.convs.append(GINEConv(mlp, train_eps=True))
            self.norms.append(nn.LayerNorm(hidden_dim))
        self.out_dim = hidden_dim * 2

    def forward(self, data) -> torch.Tensor:
        x = self.atom_in(data.x)
        edge_attr = self.edge_in(data.edge_attr)
        for conv, norm in zip(self.convs, self.norms):
            h = conv(x, data.edge_index, edge_attr)
            h = norm(h)
            h = F.relu(h)
            h = F.dropout(h, p=self.dropout, training=self.training)
            x = x + h
        pooled = torch.cat(
            [global_mean_pool(x, data.batch), global_max_pool(x, data.batch)],
            dim=-1,
        )
        return pooled


class GraphTransformerEncoder(nn.Module):
    def __init__(
        self,
        atom_dim: int,
        bond_dim: int,
        hidden_dim: int,
        layers: int,
        heads: int = 4,
        dropout: float = 0.15,
    ) -> None:
        super().__init__()
        self.atom_in = nn.Linear(atom_dim, hidden_dim)
        self.edge_in = nn.Linear(bond_dim, hidden_dim)
        self.convs = nn.ModuleList()
        self.norms_attn = nn.ModuleList()
        self.ffns = nn.ModuleList()
        self.norms_ffn = nn.ModuleList()
        self.dropout = dropout
        for _ in range(layers):
            self.convs.append(
                TransformerConv(
                    hidden_dim,
                    hidden_dim,
                    heads=heads,
                    concat=False,
                    beta=True,
                    dropout=dropout,
                    edge_dim=hidden_dim,
                )
            )
            self.norms_attn.append(nn.LayerNorm(hidden_dim))
            self.ffns.append(
                nn.Sequential(
                    nn.Linear(hidden_dim, hidden_dim * 2),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_dim * 2, hidden_dim),
                )
            )
            self.norms_ffn.append(nn.LayerNorm(hidden_dim))
        self.out_dim = hidden_dim * 2

    def forward(self, data) -> torch.Tensor:
        x = self.atom_in(data.x)
        edge_attr = self.edge_in(data.edge_attr)
        for conv, norm_attn, ffn, norm_ffn in zip(
            self.convs,
            self.norms_attn,
            self.ffns,
            self.norms_ffn,
        ):
            h = conv(x, data.edge_index, edge_attr)
            h = F.dropout(h, p=self.dropout, training=self.training)
            x = norm_attn(x + h)
            h = ffn(x)
            h = F.dropout(h, p=self.dropout, training=self.training)
            x = norm_ffn(x + h)
        return torch.cat(
            [global_mean_pool(x, data.batch), global_max_pool(x, data.batch)],
            dim=-1,
        )


class GraphOnlyModel(nn.Module):
    def __init__(
        self,
        atom_dim: int,
        bond_dim: int,
        hidden_dim: int,
        layers: int,
        out_dim: int = 1,
        dropout: float = 0.15,
    ) -> None:
        super().__init__()
        self.graph = GINEGraphEncoder(atom_dim, bond_dim, hidden_dim, layers, dropout)
        self.head = MLP(self.graph.out_dim, hidden_dim, out_dim, layers=2, dropout=dropout)

    def forward(self, data, return_aux: bool = False):
        z = self.graph(data)
        pred = self.head(z).view(-1)
        if return_aux:
            return pred, {"graph": z}
        return pred


class GraphTransformerModel(nn.Module):
    def __init__(
        self,
        atom_dim: int,
        bond_dim: int,
        hidden_dim: int,
        layers: int,
        out_dim: int = 1,
        dropout: float = 0.15,
    ) -> None:
        super().__init__()
        self.graph = GraphTransformerEncoder(atom_dim, bond_dim, hidden_dim, layers, dropout=dropout)
        self.head = MLP(self.graph.out_dim, hidden_dim, out_dim, layers=2, dropout=dropout)

    def forward(self, data, return_aux: bool = False):
        z = self.graph(data)
        pred = self.head(z).view(-1)
        if return_aux:
            return pred, {"graph": z}
        return pred


class DMPNNEncoder(nn.Module):
    def __init__(
        self,
        atom_dim: int,
        bond_dim: int,
        hidden_dim: int,
        layers: int,
        dropout: float = 0.15,
    ) -> None:
        super().__init__()
        self.atom_in = nn.Linear(atom_dim, hidden_dim)
        self.bond_in = nn.Linear(atom_dim + bond_dim, hidden_dim)
        self.message_update = nn.Linear(hidden_dim, hidden_dim)
        self.atom_out = nn.Linear(hidden_dim * 2, hidden_dim)
        self.layers = max(1, layers)
        self.dropout = dropout
        self.out_dim = hidden_dim * 2

    def forward(self, data) -> torch.Tensor:
        atom_hidden = self.atom_in(data.x)
        if data.edge_index.numel() == 0:
            node_hidden = F.relu(atom_hidden)
        else:
            src = data.edge_index[0]
            dst = data.edge_index[1]
            h0 = F.relu(self.bond_in(torch.cat([data.x[src], data.edge_attr], dim=-1)))
            message = h0
            reverse = torch.arange(message.shape[0], device=message.device)
            reverse[0::2] += 1
            reverse[1::2] -= 1
            for _ in range(self.layers):
                incoming = message.new_zeros((data.x.shape[0], message.shape[-1]))
                incoming.index_add_(0, dst, message)
                directed_context = incoming[src] - message[reverse]
                message = F.relu(h0 + self.message_update(directed_context))
                message = F.dropout(message, p=self.dropout, training=self.training)
            incoming = message.new_zeros((data.x.shape[0], message.shape[-1]))
            incoming.index_add_(0, dst, message)
            node_hidden = F.relu(self.atom_out(torch.cat([atom_hidden, incoming], dim=-1)))
        return torch.cat(
            [
                global_mean_pool(node_hidden, data.batch),
                global_max_pool(node_hidden, data.batch),
            ],
            dim=-1,
        )


class DMPNNModel(nn.Module):
    def __init__(
        self,
        atom_dim: int,
        bond_dim: int,
        hidden_dim: int,
        layers: int,
        out_dim: int = 1,
        dropout: float = 0.15,
    ) -> None:
        super().__init__()
        self.graph = DMPNNEncoder(atom_dim, bond_dim, hidden_dim, layers, dropout)
        self.head = MLP(self.graph.out_dim, hidden_dim, out_dim, layers=2, dropout=dropout)

    def forward(self, data, return_aux: bool = False):
        z = self.graph(data)
        pred = self.head(z).view(-1)
        if return_aux:
            return pred, {"graph": z}
        return pred


class FZYCMolModel(nn.Module):
    def __init__(
        self,
        atom_dim: int,
        bond_dim: int,
        fp_dim: int,
        desc_dim: int,
        hidden_dim: int,
        layers: int,
        out_dim: int = 1,
        dropout: float = 0.15,
        use_fp: bool = True,
        use_desc: bool = True,
        fusion: str = "gated",
        graph_encoder: str = "gine",
    ) -> None:
        super().__init__()
        if fusion not in {"gated", "mean"}:
            raise ValueError("fusion must be 'gated' or 'mean'.")
        self.use_fp = use_fp
        self.use_desc = use_desc
        self.fusion = fusion
        self.expert_names = ["graph"]
        if graph_encoder == "gine":
            self.graph = GINEGraphEncoder(atom_dim, bond_dim, hidden_dim, layers, dropout)
        elif graph_encoder == "transformer":
            self.graph = GraphTransformerEncoder(atom_dim, bond_dim, hidden_dim, layers, dropout=dropout)
        else:
            raise ValueError("graph_encoder must be 'gine' or 'transformer'.")
        self.graph_proj = nn.Linear(self.graph.out_dim, hidden_dim)
        if use_fp:
            self.fp_encoder = MLP(fp_dim, hidden_dim, hidden_dim, layers=2, dropout=dropout)
            self.expert_names.append("fp")
        else:
            self.fp_encoder = None
        if use_desc:
            self.desc_encoder = MLP(desc_dim, hidden_dim, hidden_dim, layers=2, dropout=dropout)
            self.expert_names.append("desc")
        else:
            self.desc_encoder = None
        if fusion == "gated":
            self.gate = nn.Sequential(
                nn.Linear(hidden_dim * len(self.expert_names), hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim, len(self.expert_names)),
            )
        else:
            self.gate = None
        self.head = MLP(hidden_dim, hidden_dim, out_dim, layers=2, dropout=dropout)

    def forward(self, data, return_aux: bool = False):
        zg = self.graph_proj(self.graph(data))
        experts = [zg]
        aux = {"graph": zg}
        if self.fp_encoder is not None:
            zf = self.fp_encoder(data.fp)
            experts.append(zf)
            aux["fp"] = zf
        if self.desc_encoder is not None:
            zd = self.desc_encoder(data.desc)
            experts.append(zd)
            aux["desc"] = zd
        stacked = torch.stack(experts, dim=1)
        if self.gate is not None:
            gate_logits = self.gate(torch.cat(experts, dim=-1))
            weights = torch.softmax(gate_logits, dim=-1)
        else:
            weights = torch.full(
                (stacked.shape[0], stacked.shape[1]),
                fill_value=1.0 / stacked.shape[1],
                device=stacked.device,
                dtype=stacked.dtype,
            )
        fused = (stacked * weights.unsqueeze(-1)).sum(dim=1)
        pred = self.head(fused).view(-1)
        if return_aux:
            aux.update({"gate": weights, "fused": fused})
            return pred, aux
        return pred


def contrastive_alignment_loss(z1: torch.Tensor, z2: torch.Tensor, temperature: float = 0.2) -> torch.Tensor:
    if z1.shape[0] <= 1:
        return z1.new_tensor(0.0)
    z1 = F.normalize(z1, dim=-1)
    z2 = F.normalize(z2, dim=-1)
    logits = z1 @ z2.t() / temperature
    labels = torch.arange(z1.shape[0], device=z1.device)
    loss_12 = F.cross_entropy(logits, labels)
    loss_21 = F.cross_entropy(logits.t(), labels)
    return 0.5 * (loss_12 + loss_21)
