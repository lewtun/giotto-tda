"""The module :mod:`giotto.diagram` implements persistence diagrams
transformers.
It offers the possibility to stack across homology dimensions,
scale, and filter diagrams.
It also makes it possible to calculate distance matrices.
"""

from .distance import DiagramDistance, DiagramAmplitude
from .features import PersistentEntropy, BettiCurve, PersistenceLandscape, HeatKernel
from .preprocessing import DiagramStacker, DiagramScaler, DiagramFilter

__all__ = [
    'DiagramStacker',
    'DiagramScaler',
    'DiagramFilter',
    'DiagramDistance',
    'DiagramAmplitude',
    'PersistentEntropy',
    'BettiCurve',
    'PersistenceLandscape'
    'HeatKernel'
]
