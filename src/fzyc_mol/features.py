from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
import torch
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import AllChem, Crippen, Descriptors, Lipinski, MACCSkeys, rdFingerprintGenerator, rdMolDescriptors
from rdkit.Chem.Scaffolds import MurckoScaffold
from torch_geometric.data import Data


RDLogger.DisableLog("rdApp.*")

ATOM_NUMBERS = [1, 5, 6, 7, 8, 9, 11, 12, 15, 16, 17, 19, 20, 35, 53]
BOND_TYPES = [
    Chem.BondType.SINGLE,
    Chem.BondType.DOUBLE,
    Chem.BondType.TRIPLE,
    Chem.BondType.AROMATIC,
]
HYBRIDIZATIONS = [
    Chem.HybridizationType.SP,
    Chem.HybridizationType.SP2,
    Chem.HybridizationType.SP3,
    Chem.HybridizationType.SP3D,
    Chem.HybridizationType.SP3D2,
]


def mol_from_smiles(smiles: str) -> Chem.Mol | None:
    if not isinstance(smiles, str):
        return None
    return Chem.MolFromSmiles(smiles)


def scaffold_from_smiles(smiles: str) -> str:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return ""
    try:
        scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
        return scaffold or Chem.MolToSmiles(mol, canonical=True, isomericSmiles=False)
    except Exception:
        Chem.RemoveStereochemistry(mol)
        return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=False)


def one_hot(value, choices: list | tuple) -> list[float]:
    return [float(value == choice) for choice in choices] + [float(value not in choices)]


def atom_features(atom: Chem.Atom) -> list[float]:
    features: list[float] = []
    features += one_hot(atom.GetAtomicNum(), ATOM_NUMBERS)
    features += one_hot(atom.GetDegree(), [0, 1, 2, 3, 4, 5])
    features += one_hot(atom.GetFormalCharge(), [-2, -1, 0, 1, 2])
    features += one_hot(atom.GetHybridization(), HYBRIDIZATIONS)
    features.append(float(atom.GetIsAromatic()))
    features.append(float(atom.IsInRing()))
    features.append(float(atom.GetTotalNumHs(includeNeighbors=True)) / 4.0)
    features.append(float(atom.GetMass()) / 200.0)
    return features


def bond_features(bond: Chem.Bond) -> list[float]:
    features: list[float] = []
    features += one_hot(bond.GetBondType(), BOND_TYPES)
    features.append(float(bond.GetIsConjugated()))
    features.append(float(bond.IsInRing()))
    stereo = int(bond.GetStereo())
    features.append(float(stereo) / 6.0)
    return features


def morgan_fingerprint(smiles: str, n_bits: int = 2048, radius: int = 2) -> np.ndarray:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return np.zeros(n_bits, dtype=np.float32)
    generator = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=n_bits)
    bitvect = generator.GetFingerprint(mol)
    arr = np.zeros((n_bits,), dtype=np.int8)
    DataStructs.ConvertToNumpyArray(bitvect, arr)
    return arr.astype(np.float32)


def _bitvect_to_array(bitvect, n_bits: int | None = None) -> np.ndarray:
    size = int(n_bits or bitvect.GetNumBits())
    arr = np.zeros((size,), dtype=np.int8)
    DataStructs.ConvertToNumpyArray(bitvect, arr)
    return arr.astype(np.float32)


def morgan_feature_fingerprint(smiles: str, n_bits: int = 2048, radius: int = 2) -> np.ndarray:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return np.zeros(n_bits, dtype=np.float32)
    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=radius,
        fpSize=n_bits,
        atomInvariantsGenerator=rdFingerprintGenerator.GetMorganFeatureAtomInvGen(),
    )
    return _bitvect_to_array(generator.GetFingerprint(mol), n_bits)


def maccs_fingerprint(smiles: str) -> np.ndarray:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return np.zeros(167, dtype=np.float32)
    return _bitvect_to_array(MACCSkeys.GenMACCSKeys(mol), 167)


def rdkit_topological_fingerprint(smiles: str, n_bits: int = 2048) -> np.ndarray:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return np.zeros(n_bits, dtype=np.float32)
    return _bitvect_to_array(Chem.RDKFingerprint(mol, fpSize=n_bits), n_bits)


def atom_pair_fingerprint(smiles: str, n_bits: int = 2048) -> np.ndarray:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return np.zeros(n_bits, dtype=np.float32)
    return _bitvect_to_array(rdMolDescriptors.GetHashedAtomPairFingerprintAsBitVect(mol, nBits=n_bits), n_bits)


def torsion_fingerprint(smiles: str, n_bits: int = 2048) -> np.ndarray:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return np.zeros(n_bits, dtype=np.float32)
    return _bitvect_to_array(
        rdMolDescriptors.GetHashedTopologicalTorsionFingerprintAsBitVect(mol, nBits=n_bits),
        n_bits,
    )


def multi_fingerprint_vector(smiles: str) -> np.ndarray:
    return np.hstack(
        [
            morgan_fingerprint(smiles, radius=2),
            morgan_feature_fingerprint(smiles, n_bits=1024, radius=2),
            rdkit_topological_fingerprint(smiles, n_bits=1024),
            atom_pair_fingerprint(smiles, n_bits=1024),
            torsion_fingerprint(smiles, n_bits=1024),
            maccs_fingerprint(smiles),
            descriptor_vector(smiles),
        ]
    ).astype(np.float32)


def _safe_float(value: float) -> float:
    if value is None or not math.isfinite(float(value)):
        return 0.0
    return float(value)


def _conformer_descriptors(mol: Chem.Mol) -> list[float]:
    uff_friendly_atoms = {1, 5, 6, 7, 8, 9, 14, 15, 16, 17, 35, 53}
    heavy_atoms = mol.GetNumHeavyAtoms()
    if heavy_atoms > 80 or any(atom.GetAtomicNum() not in uff_friendly_atoms for atom in mol.GetAtoms()):
        return [0.0] * 8
    try:
        work = Chem.AddHs(mol)
        params = AllChem.ETKDGv3()
        params.randomSeed = 61453
        status = AllChem.EmbedMolecule(work, params)
        if status != 0:
            return [0.0] * 8
        AllChem.UFFOptimizeMolecule(work, maxIters=80)
        values = [
            rdMolDescriptors.CalcPMI1(work),
            rdMolDescriptors.CalcPMI2(work),
            rdMolDescriptors.CalcPMI3(work),
            rdMolDescriptors.CalcNPR1(work),
            rdMolDescriptors.CalcNPR2(work),
            rdMolDescriptors.CalcRadiusOfGyration(work),
            rdMolDescriptors.CalcInertialShapeFactor(work),
            rdMolDescriptors.CalcAsphericity(work),
        ]
        return [_safe_float(v) for v in values]
    except Exception:
        return [0.0] * 8


@lru_cache(maxsize=200_000)
def descriptor_vector(smiles: str, include_3d: bool = True) -> np.ndarray:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return np.zeros(28, dtype=np.float32)
    values = [
        Descriptors.MolWt(mol),
        Descriptors.HeavyAtomMolWt(mol),
        Descriptors.ExactMolWt(mol),
        Crippen.MolLogP(mol),
        Crippen.MolMR(mol),
        rdMolDescriptors.CalcTPSA(mol),
        Lipinski.NumHDonors(mol),
        Lipinski.NumHAcceptors(mol),
        Lipinski.NumRotatableBonds(mol),
        Lipinski.RingCount(mol),
        Lipinski.NumAromaticRings(mol),
        Lipinski.NumAliphaticRings(mol),
        Lipinski.NumSaturatedRings(mol),
        rdMolDescriptors.CalcFractionCSP3(mol),
        rdMolDescriptors.CalcNumHeteroatoms(mol),
        rdMolDescriptors.CalcNumAmideBonds(mol),
        rdMolDescriptors.CalcLabuteASA(mol),
        rdMolDescriptors.CalcHallKierAlpha(mol),
        Descriptors.BalabanJ(mol),
        Descriptors.BertzCT(mol),
    ]
    if include_3d:
        values += _conformer_descriptors(mol)
    else:
        values += [0.0] * 8
    return np.asarray([_safe_float(v) for v in values], dtype=np.float32)


def smiles_to_graph(
    smiles: str,
    y: float | int,
    task_type: str,
    include_3d: bool = True,
    n_bits: int = 2048,
) -> Data:
    mol = mol_from_smiles(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES: {smiles}")

    x = torch.tensor([atom_features(atom) for atom in mol.GetAtoms()], dtype=torch.float32)
    edge_index: list[list[int]] = []
    edge_attr: list[list[float]] = []
    for bond in mol.GetBonds():
        i = bond.GetBeginAtomIdx()
        j = bond.GetEndAtomIdx()
        bf = bond_features(bond)
        edge_index.extend([[i, j], [j, i]])
        edge_attr.extend([bf, bf])

    if edge_index:
        edge_index_tensor = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
        edge_attr_tensor = torch.tensor(edge_attr, dtype=torch.float32)
    else:
        edge_index_tensor = torch.empty((2, 0), dtype=torch.long)
        edge_attr_tensor = torch.empty((0, len(bond_features(Chem.MolFromSmiles("CC").GetBondWithIdx(0)))), dtype=torch.float32)

    target_dtype = torch.float32
    y_tensor = torch.tensor([float(y)], dtype=target_dtype)
    data = Data(
        x=x,
        edge_index=edge_index_tensor,
        edge_attr=edge_attr_tensor,
        y=y_tensor,
    )
    data.fp = torch.tensor(morgan_fingerprint(smiles, n_bits=n_bits), dtype=torch.float32).view(1, -1)
    data.desc = torch.tensor(descriptor_vector(smiles, include_3d=include_3d), dtype=torch.float32).view(1, -1)
    data.smiles = smiles
    data.task_type = task_type
    return data


def feature_dimensions() -> tuple[int, int, int]:
    atom_dim = len(atom_features(Chem.MolFromSmiles("C").GetAtomWithIdx(0)))
    bond_dim = len(bond_features(Chem.MolFromSmiles("CC").GetBondWithIdx(0)))
    desc_dim = int(descriptor_vector("CCO").shape[0])
    return atom_dim, bond_dim, desc_dim
