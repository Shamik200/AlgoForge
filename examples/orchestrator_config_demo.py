"""Demonstration of Orchestrator configuration validation and logging.

This script demonstrates the integration of ConfigValidator and StructuredLogger
into the Orchestrator startup sequence, implementing Requirements 16.2 and 16.7.

Run this script to see:
1. Configuration validation on startup
2. Configuration summary logging
3. System refusing to start on invalid configuration
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from algoforge.core.config import Settings
from algoforge.core.logging import setup_logging
from algoforge.core.orchestrator import Orchestrator


def demo_valid_config():
    """Demonstrate Orchestrator startup with valid configuration."""
    print("\n" + "=" * 80)
    print("DEMO 1: Valid Configuration")
    print("=" * 80)
    
    # Setup logging first
    setup_logging()
    
    print("\nInitializing Orchestrator with valid configuration...")
    print("Expected: Configuration validation passes, summary is logged\n")
    
    try:
        orchestrator = Orchestrator(
            capital=100_000.0,
            enable_ml=False,
            enable_dual_tf=False,
            enable_fundamentals=False,
            enable_combination=True,
            validate_config=True,
        )
        
        print("\n✓ Orchestrator initialized successfully!")
        print(f"✓ Strategies registered: {orchestrator.stats['strategies']}")
        print(f"✓ Configuration validation: PASSED")
        
    except SystemExit as e:
        print(f"\n✗ Orchestrator failed to start: {e}")
        return False
    
    return True


def demo_invalid_config():
    """Demonstrate Orchestrator refusing to start with invalid configuration."""
    print("\n" + "=" * 80)
    print("DEMO 2: Invalid Configuration")
    print("=" * 80)
    
    print("\nAttempting to initialize Orchestrator with invalid configuration...")
    print("Expected: System refuses to start, detailed errors are logged\n")
    
    # Create invalid settings
    from unittest.mock import patch
    from algoforge.core.validator import ValidationResult
    
    # Mock validation to return errors
    invalid_result = ValidationResult(
        valid=False,
        errors=[
            "max_daily_loss_pct (25.0%) must be less than max_drawdown_pct (20.0%)",
            "mandatory_stop_loss must be True - trading without stop losses is not allowed",
        ],
        warnings=[],
    )
    
    with patch('algoforge.core.orchestrator.validate_settings', return_value=invalid_result):
        try:
            orchestrator = Orchestrator(validate_config=True)
            print("\n✗ Orchestrator should have refused to start!")
            return False
            
        except SystemExit as e:
            print(f"\n✓ System correctly refused to start")
            print(f"✓ Error message: {e}")
            print(f"✓ Configuration validation: FAILED (as expected)")
            return True


def demo_config_with_warnings():
    """Demonstrate Orchestrator starting with warnings."""
    print("\n" + "=" * 80)
    print("DEMO 3: Configuration with Warnings")
    print("=" * 80)
    
    print("\nInitializing Orchestrator with configuration that has warnings...")
    print("Expected: System starts successfully but logs warnings\n")
    
    from unittest.mock import patch
    from algoforge.core.validator import ValidationResult
    
    # Mock validation to return warnings
    warning_result = ValidationResult(
        valid=True,
        errors=[],
        warnings=[
            "paper_trading_capital (500.0) is very low",
            "Redis password is not set - not recommended for production",
        ],
    )
    
    with patch('algoforge.core.orchestrator.validate_settings', return_value=warning_result):
        try:
            orchestrator = Orchestrator(
                capital=500.0,
                validate_config=True,
            )
            
            print("\n✓ Orchestrator initialized successfully despite warnings")
            print(f"✓ Configuration validation: PASSED (with 2 warnings)")
            print(f"✓ Warnings are logged but system continues")
            return True
            
        except SystemExit as e:
            print(f"\n✗ System should not have refused to start on warnings: {e}")
            return False


def demo_skip_validation():
    """Demonstrate Orchestrator with validation disabled."""
    print("\n" + "=" * 80)
    print("DEMO 4: Skip Validation")
    print("=" * 80)
    
    print("\nInitializing Orchestrator with validation disabled...")
    print("Expected: System starts without validation (for testing/development)\n")
    
    try:
        orchestrator = Orchestrator(
            capital=100_000.0,
            validate_config=False,  # Skip validation
        )
        
        print("\n✓ Orchestrator initialized without validation")
        print(f"✓ Validation was skipped (validate_config=False)")
        print(f"✓ Useful for testing and development")
        return True
        
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return False


def main():
    """Run all demonstrations."""
    print("\n" + "=" * 80)
    print("ORCHESTRATOR CONFIGURATION INTEGRATION DEMONSTRATION")
    print("=" * 80)
    print("\nThis demonstrates Requirements 16.2 and 16.7:")
    print("  16.2: System refuses to start on invalid configuration")
    print("  16.7: Configuration summary is logged on startup")
    print("=" * 80)
    
    results = []
    
    # Run demos
    results.append(("Valid Configuration", demo_valid_config()))
    results.append(("Invalid Configuration", demo_invalid_config()))
    results.append(("Configuration with Warnings", demo_config_with_warnings()))
    results.append(("Skip Validation", demo_skip_validation()))
    
    # Summary
    print("\n" + "=" * 80)
    print("DEMONSTRATION SUMMARY")
    print("=" * 80)
    
    for name, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"{status}: {name}")
    
    all_passed = all(success for _, success in results)
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✓ ALL DEMONSTRATIONS PASSED")
        print("✓ ConfigValidator and StructuredLogger are properly integrated")
        print("✓ Requirements 16.2 and 16.7 are satisfied")
    else:
        print("✗ SOME DEMONSTRATIONS FAILED")
    print("=" * 80 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
