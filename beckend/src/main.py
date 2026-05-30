"""
Main  orchestrator for the Excel Relationship Discovery System.
Ties all components together.
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger
from datetime import datetime
import sys
import threading

from src.config import Config
from src.excel_loader import ExcelLoader
from src.profiling_engine import ProfilingEngine
from src.relationship_detector import RelationshipDetector
from src.llm_reasoner import LLMReasoner
from src.business_validator import BusinessContextValidator
from src.progress_callback import ProgressCallback, NoOpProgressCallback, Stage


class RelationshipDiscovery:
    """
    Main orchestrator for discovering relationships between Excel files.
    """
    
    def __init__(self):
        self.loader = ExcelLoader()
        self.profiler = ProfilingEngine()
        self.llm_reasoner = LLMReasoner()
        self.business_validator = BusinessContextValidator()
        
        # Configure logging
        logger.remove()
        logger.add(
            sys.stderr,
            level=Config.LOG_LEVEL,
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
        )
    
    def discover_relationships(
        self,
        file_paths: List[str],
        output_file: str = None,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_event: Optional[threading.Event] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for relationship discovery.

        Args:
            file_paths: List of paths to Excel files
            output_file: Optional path for JSON report output
            progress_callback: Optional progress callback for tracking
            cancel_event: Optional threading event for cancellation

        Returns:
            Dictionary containing the complete relationship report
        """
        # Use no-op callback if none provided (backward compatibility)
        if progress_callback is None:
            progress_callback = NoOpProgressCallback()

        logger.info("="* 60)
        logger.info("Excel Relationship Discovery System")
        logger.info("="* 60)
        
        # Display configuration
        if Config.LOG_LEVEL == "DEBUG":
            print(Config.summary())
        
        start_time = datetime.now()
        
        try:
            # Step 1: Load and validate files
            logger.info("\n[Step 1/6] Loading Excel files...")
            progress_callback.set_stage(Stage.LOADING, len(file_paths))

            dataframes = self.loader.load_files(file_paths)

            for file_path in file_paths:
                progress_callback.increment(f"Loaded {Path(file_path).name}")

            # Step 2: Profile all columns
            logger.info("\n[Step 2/6] Profiling data...")
            progress_callback.set_stage(Stage.PROFILING, sum(len(df.columns) for df in dataframes.values()))

            profiles = self.profiler.profile_all_files(dataframes)
            # Note: profiling_engine will call increment for each column

            # Step 3: Generate relationship candidates
            logger.info("\n[Step 3/6] Detecting relationships...")
            progress_callback.set_stage(Stage.DETECTING, len(file_paths) * (len(file_paths) - 1))

            detector = RelationshipDetector(profiles, dataframes)
            candidates = detector.generate_candidates()

            progress_callback.increment(f"Found {len(candidates)} candidate relationships")

            # Step 4: LLM semantic validation (for medium/low confidence only)
            logger.info("\n[Step 4/6] LLM semantic validation...")
            llm_candidates = [c for c in candidates if c.requires_llm_validation]
            progress_callback.set_stage(Stage.LLM_VALIDATION, len(llm_candidates) if llm_candidates else 1)

            validated_candidates = self._llm_validation_phase(candidates, profiles, progress_callback)

            # Step 5: Validate relationships
            logger.info("\n[Step 5/6] Validating relationships...")
            validated_relationships = self._validation_phase(validated_candidates, dataframes)

            # Step 5.5: BUSINESS CONTEXT VALIDATION (Per-Relationship Analysis!)
            # Validate EACH relationship individually to get specific insights
            logger.info("\n[Step 5.5/6] 🌟 Validating business context for each relationship...")
            progress_callback.set_stage(Stage.BUSINESS_VALIDATION, len(validated_relationships) if validated_relationships else 1)

            for i, relationship in enumerate(validated_relationships):
                relationship.business_insights = self.business_validator.validate_single_relationship(
                    relationship,
                    profiles[relationship.source_file],
                    profiles[relationship.target_file]
                )
                progress_callback.increment(f"Validated relationship {i+1}/{len(validated_relationships)}")

            # Step 6: Generate JSON report
            logger.info("\n[Step 6/6] Generating JSON report...")
            progress_callback.set_stage(Stage.REPORTING, 1)

            report = self._generate_report(
                profiles,
                validated_relationships,
                start_time
            )

            progress_callback.increment("Report generated")
            
            # Save report
            if output_file:
                self._save_report(report, output_file)
            else:
                # Auto-generate filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                default_output = f"output/relationship_report_{timestamp}.json"
                self._save_report(report, default_output)
            
            # Summary
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info("\n" + "="* 60)
            logger.success(f"✓ Discovery complete in {duration:.1f}s")
            logger.info(f"  Files analyzed: {len(dataframes)}")
            logger.info(f"  Relationships found: {len(validated_relationships)}")
            logger.info(f"  High confidence: {sum(1 for r in validated_relationships if r.confidence_level == 'HIGH')}")
            logger.info(f"  Medium confidence: {sum(1 for r in validated_relationships if r.confidence_level == 'MEDIUM')}")
            logger.info(f"  Low confidence: {sum(1 for r in validated_relationships if r.confidence_level == 'LOW')}")
            
            # Business insights summary
            relationships_with_insights = sum(
                1 for r in validated_relationships 
                if r.business_insights and r.business_insights.get("is_relationship_helpful") in ["ESSENTIAL", "HELPFUL"]
            )
            if relationships_with_insights > 0:
                logger.success(f"  🌟 Business Insights: {relationships_with_insights} relationships analyzed")
                essential_count = sum(
                    1 for r in validated_relationships
                    if r.business_insights and r.business_insights.get("is_relationship_helpful") == "ESSENTIAL"
                )
                if essential_count > 0:
                    logger.info(f"     {essential_count} ESSENTIAL relationships identified")
            
            logger.info("="* 60)
            
            return report
            
        except Exception as e:
            logger.error(f"\n✗ Discovery failed: {e}")
            raise
    
    def _llm_validation_phase(self, candidates, profiles, progress_callback: ProgressCallback):
        """Apply LLM validation to candidates that require it."""
        validated = []

        llm_candidates = [c for c in candidates if c.requires_llm_validation and Config.ENABLE_LLM_VALIDATION]

        for i, candidate in enumerate(candidates):
            if candidate.requires_llm_validation and Config.ENABLE_LLM_VALIDATION:
                # Prepare candidate data for LLM
                llm_input = {
                    "source": {
                        "file": candidate.source_file,
                        "column": candidate.source_column,
                        **self._get_column_data(profiles, candidate.source_file, candidate.source_column)
                    },
                    "target": {
                        "file": candidate.target_file,
                        "column": candidate.target_column,
                        **self._get_column_data(profiles, candidate.target_file, candidate.target_column)
                    },
                    "statistics": candidate.statistics
                }

                # Validate with LLM
                llm_result = self.llm_reasoner.validate_relationship(llm_input)

                # Update candidate with LLM result
                if llm_result.get("is_related"):
                    candidate.confidence_score = llm_result.get("confidence_score", candidate.confidence_score)
                    candidate.relationship_type = llm_result.get("relationship_type", candidate.relationship_type)
                    if llm_result.get("warnings"):
                        candidate.warnings.extend(llm_result["warnings"])
                    validated.append(candidate)

                # Report progress
                progress_callback.increment(f"Validated {candidate.source_column} → {candidate.target_column}")
            else:
                validated.append(candidate)

        # If no LLM candidates, still report progress
        if not llm_candidates:
            progress_callback.increment("No LLM validation required")

        return validated
    
    def _get_column_data(self, profiles, file_path, column_name):
        """Get column profile data."""
        col_profile = profiles.get(file_path, {}).get("columns", {}).get(column_name, {})
        return {
            "data_type": col_profile.get("data_type"),
            "sample_values": col_profile.get("sample_values", []),
            "uniqueness": col_profile.get("unique_percent", 0) /100,
            "null_percent": col_profile.get("null_percent", 0)
        }
    
    def _validation_phase(self, candidates, dataframes):
        """Validate all relationships."""
        # For now, just return candidates
        # In full implementation, would do referential integrity checks, etc.
        return candidates
    
    def _generate_report(self, profiles, relationships, start_time):
        """Generate final JSON report."""
        from pathlib import Path
        
        end_time = datetime.now()
        
        report = {
            "report_metadata": {
                "generated_at": end_time.isoformat(),
                "file_count": len(profiles),
                "total_relationships_found": len(relationships),
                "high_confidence": sum(1 for r in relationships if r.confidence_level == "HIGH"),
                "medium_confidence": sum(1 for r in relationships if r.confidence_level == "MEDIUM"),
                "low_confidence": sum(1 for r in relationships if r.confidence_level == "LOW"),
                "processing_time_seconds": (end_time - start_time).total_seconds()
            },
            "files": [],
            "relationships": [],  # Each relationship now includes its own business_insights
            "recommendations": []
        }
        
        # Add file profiles
        for file_path, file_profile in profiles.items():
            report["files"].append({
                "file_name": Path(file_path).name,
                "file_path": file_path,
                "row_count": file_profile["row_count"],
                "column_count": file_profile["column_count"],
                "columns": [
                    {
                        **col_data,
                        "name": col_name
                    }
                    for col_name, col_data in file_profile["columns"].items()
                ]
            })
        
        # Add relationships
        for rel in relationships:
            report["relationships"].append(rel.to_dict())
        
        # Add recommendations
        for rel in relationships:
            if rel.warnings:
                for warning in rel.warnings:
                    report["recommendations"].append({
                        "type": "DATA_QUALITY",
                        "severity": "MEDIUM",
                        "message": f"{rel.source_column} <-> {rel.target_column}: {warning}"
                    })
        
        return report
    
    def _save_report(self, report, output_file):
        """Save report to JSON file."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        import json
        with open(output_path, 'w', encoding='utf-8') as f:
            if Config.PRETTY_PRINT_JSON:
                json.dump(report, f, indent=2, ensure_ascii=False)
            else:
                json.dump(report, f, ensure_ascii=False)
        
        logger.success(f"✓ Report saved to: {output_path}")


def main():
    """Command-line entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Discover relationships between Excel files"
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Excel files to analyze"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output JSON file path",
        default=None
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM validation"
    )
    
    args = parser.parse_args()
    
    # Override config if needed
    if args.no_llm:
        Config.ENABLE_LLM_VALIDATION = False
    
    # Run discovery
    discovery = RelationshipDiscovery()
    discovery.discover_relationships(args.files, args.output)


if __name__ == "__main__":
    main()
