"""Proximity detection for testing structural levels."""

from typing import Optional

from algoforge.technical.structural.engine import StructuralSnapshot
from algoforge.technical.structural.models import SRLevel


def find_tested_levels(
    high_p: float,
    low_p: float,
    atr_val: float,
    snapshot: StructuralSnapshot
) -> tuple[Optional[SRLevel], Optional[SRLevel]]:
    """Find the highest-confluence support and resistance level currently tested by price.
    
    A level is "tested" if it falls between (Low - 0.5*ATR) and (High + 0.5*ATR).
    If multiple levels are tested, the one with the highest confluence_score is returned.
    
    Args:
        high_p: Current bar High.
        low_p: Current bar Low.
        atr_val: Current ATR(14) value.
        snapshot: The StructuralSnapshot containing SRLevels.
        
    Returns:
        Tuple of (Tested Support Level, Tested Resistance Level).
    """
    if atr_val <= 0.0 or snapshot is None:
        return None, None
        
    proximity_band = 0.5 * atr_val
    upper_bound = high_p + proximity_band
    lower_bound = low_p - proximity_band
    
    best_support: Optional[SRLevel] = None
    best_resistance: Optional[SRLevel] = None
    
    # Check Support
    for level in snapshot.support_levels:
        if lower_bound <= level.price <= upper_bound:
            if best_support is None or level.strength > best_support.strength:
                best_support = level
                
    # Check Resistance
    for level in snapshot.resistance_levels:
        if lower_bound <= level.price <= upper_bound:
            if best_resistance is None or level.strength > best_resistance.strength:
                best_resistance = level
                
    return best_support, best_resistance


def check_htf_overlap(
    tested_level: SRLevel,
    atr_val: float,
    htf_snapshots: list[StructuralSnapshot]
) -> bool:
    """Check if the tested level is corroborated by a Higher Timeframe snapshot.
    
    Args:
        tested_level: The LTF SRLevel being tested.
        atr_val: The LTF ATR value for the proximity band.
        htf_snapshots: List of HTF StructuralSnapshots to cross-reference.
        
    Returns:
        True if an HTF level exists within 0.5 * ATR of the tested level.
    """
    if not htf_snapshots or atr_val <= 0.0:
        return False
        
    proximity_band = 0.5 * atr_val
    upper_bound = tested_level.price + proximity_band
    lower_bound = tested_level.price - proximity_band
    
    for htf_snap in htf_snapshots:
        # Check all HTF support and resistance levels
        all_htf_levels = htf_snap.support_levels + htf_snap.resistance_levels
        for htf_level in all_htf_levels:
            if lower_bound <= htf_level.price <= upper_bound:
                return True
                
    return False
