"""
Multi-factor signal scoring engine.
Implements quantitative conviction scoring across five dimensions.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np
from sqlalchemy.orm import Session
from src.models.signals import Signal
from src.utils.logging import get_logger

logger = get_logger(__name__)

@dataclass
class ScoringFactors:
    """Raw factors for signal scoring."""
    recency_score: float
    size_score: float
    competence_score: float
    consensus_score: float
    regime_score: float

class SignalScorer:
    """
    Quantifies conviction for each trade signal.
    
    Scoring Process:
    1. Calculate 5 individual factor scores (0.0 to 1.0)
    2. Apply weights to factors
    3. Generate total score (0.0 to 1.0)
    4. Assign conviction tier (S/A/B/C/REJECT)
    """
    
    WEIGHTS = {
        'recency': 0.25,
        'size': 0.20,
        'competence': 0.30,
        'consensus': 0.15,
        'regime': 0.10
    }
    
    TIER_THRESHOLDS = {
        'S': 0.80,
        'A': 0.65,
        'B': 0.50,
        'C': 0.35,
        'REJECT': 0.00
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    def score_signal(
        self,
        signal: Dict,
        similar_signals: List[Signal],
        filer_history: Optional[Dict] = None
    ) -> ScoringFactors:
        """Score a signal across all dimensions."""
        recency = self._score_recency(signal['filing_date'])
        size = self._score_size(signal['transaction_value'], signal['symbol'])
        competence = self._score_competence(signal.get('filer_cik'), filer_history)
        consensus = self._score_consensus(similar_signals)
        regime = self._score_regime(signal['symbol'])
        
        logger.info(
            "Signal scored",
            signal_id=signal.get('signal_id'),
            recency=recency,
            size=size,
            competence=competence,
            consensus=consensus,
            regime=regime
        )
        
        return ScoringFactors(
            recency_score=recency,
            size_score=size,
            competence_score=competence,
            consensus_score=consensus,
            regime_score=regime
        )
    
    def _score_recency(self, filing_date: datetime) -> float:
        """Score based on how recent the signal is."""
        days_ago = (datetime.utcnow() - filing_date).days
        
        if days_ago <= 0:
            return 1.0
        elif days_ago >= 90:
            return 0.0
        else:
            return max(0.0, 1.0 - (days_ago / 90.0))
    
    def _score_size(self, transaction_value: float, symbol: str) -> float:
        """Score based on transaction size."""
        if transaction_value >= 10_000_000:
            return 1.0
        elif transaction_value >= 1_000_000:
            return 0.8
        elif transaction_value >= 100_000:
            return 0.5
        elif transaction_value >= 10_000:
            return 0.3
        else:
            return 0.1
    
    def _score_competence(self, filer_cik: str, filer_history: Optional[Dict]) -> float:
        """Score based on filer's historical accuracy."""
        if not filer_history:
            return 0.5
        
        win_rate = filer_history.get('win_rate', 0.5)
        sample_size = filer_history.get('trades_tracked', 0)
        
        if sample_size < 5:
            confidence = sample_size / 5.0
            return 0.5 + (win_rate - 0.5) * confidence
        
        return win_rate
    
    def _score_consensus(self, similar_signals: List[Signal]) -> float:
        """Score based on how many similar signals exist."""
        count = len(similar_signals)
        
        if count >= 4:
            return 1.0
        elif count == 3:
            return 0.8
        elif count == 2:
            return 0.6
        elif count == 1:
            return 0.3
        else:
            return 0.0
    
    def _score_regime(self, symbol: str) -> float:
        """Score based on current market regime."""
        return 0.5
    
    def calculate_total_score(self, factors: ScoringFactors) -> float:
        """Compute weighted total conviction score."""
        total = (
            factors.recency_score * self.WEIGHTS['recency'] +
            factors.size_score * self.WEIGHTS['size'] +
            factors.competence_score * self.WEIGHTS['competence'] +
            factors.consensus_score * self.WEIGHTS['consensus'] +
            factors.regime_score * self.WEIGHTS['regime']
        )
        return round(total, 4)
    
    def assign_tier(self, total_score: float) -> str:
        """Map total score to conviction tier."""
        for tier, threshold in self.TIER_THRESHOLDS.items():
            if total_score >= threshold:
                return tier
        return 'REJECT'
