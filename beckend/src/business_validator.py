"""
Business Context Validator - Domain-Agnostic Analysis
Validates if discovered relationships tell a complete business story across ANY data domain.
Asks critical questions about relationship validity, data coherence, and actionable insights.
"""

from typing import Dict, List, Any, Optional
from loguru import logger

from src.config import Config
from src.llm_reasoner import LLMReasoner


class BusinessContextValidator:
    """
    Validates if discovered relationships connect scattered business information
    into a coherent narrative. Goes beyond technical joins to assess business value.
    
    **This is what makes the system stand out:**
    - Not just "Can these columns join?" 
    - But "Do these joins reveal the complete business story?"
    """
    
    def __init__(self):
        self.llm = LLMReasoner()
    
    def validate_single_relationship(
        self,
        relationship: Any,
        source_profile: Dict[str, Any],
        target_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate a SINGLE relationship and generate business insights specific to it.
        
        This method asks: "What does THIS specific relationship reveal?"
        
        Args:
            relationship: Single relationship candidate
            source_profile: Profile of the source file
            target_profile: Profile of the target file
            
        Returns:
            Dictionary with business insights for this relationship
        """
        if not Config.ENABLE_LLM_VALIDATION:
            return self._get_fallback_single_relationship_insights()
       
        logger.info(f"  Analyzing: {relationship.source_column} → {relationship.target_column}")
        
        # Build context for this specific relationship
        context = self._build_single_relationship_context(
            relationship, source_profile, target_profile
        )
        
        # Ask LLM about this specific relationship
        insights = self._ask_llm_single_relationship(context)
        
        return insights
    
    def validate_business_context(
        self,
        profiles: Dict[str, Dict[str, Any]],
        relationships: List[Any]
    ) -> Dict[str, Any]:
        """
        Validate if the discovered relationships create a complete business view.
        
        Args:
            profiles: File profiles with column metadata
            relationships: Discovered relationship candidates
            
        Returns:
            Dictionary with business insights
        """
        if not Config.ENABLE_LLM_VALIDATION:
            return self._get_fallback_insights()
        
        logger.info("Analyzing business context...")
        
        # Build business context map
        context = self._build_business_context(profiles, relationships)
        
        # Ask LLM: "Does this tell a complete story?"
        business_insights = self._ask_llm_business_questions(context)
        
        return business_insights
    
    def _build_business_context(
        self,
        profiles: Dict[str, Dict[str, Any]],
        relationships: List[Any]
    ) -> Dict[str, Any]:
        """Build a business-focused context from technical metadata."""
        from pathlib import Path
        
        # Extract file names and their business entities
        files_summary = {}
        for file_path, profile in profiles.items():
            file_name = Path(file_path).stem
            
            # Infer business entity from file name and columns
            entity_type = self._infer_business_entity(file_name, profile)
            
            key_columns = [
                col_name for col_name, col_data in profile["columns"].items()
                if col_data.get("key_features", {}).get("primary_key_candidate") or
                   col_data.get("key_features", {}).get("foreign_key_candidate")
            ]
            
            files_summary[file_name] = {
                "entity_type": entity_type,
                "row_count": profile["row_count"],
                "key_columns": key_columns,
                "all_columns": list(profile["columns"].keys())
            }
        
        # Summarize relationships
        relationships_summary = []
        for rel in relationships:
            if rel.confidence_level in ["HIGH", "MEDIUM"]:
                relationships_summary.append({
                    "from": f"{Path(rel.source_file).stem}.{rel.source_column}",
                    "to": f"{Path(rel.target_file).stem}.{rel.target_column}",
                    "type": rel.relationship_type,
                    "confidence": rel.confidence_level
                })
        
        return {
            "files": files_summary,
            "relationships": relationships_summary,
            "file_count": len(profiles)
        }
    
    def _infer_business_entity(self, file_name: str, profile: Dict) -> str:
        """Infer generic business entity type from file name and column patterns."""
        name_lower = file_name.lower()
        columns_lower = [col.lower() for col in profile.get("columns", {}).keys()]
        
        # Master Data Entities (relatively stable, reference data)
        if any(kw in name_lower for kw in ['customer', 'client', 'user', 'member', 'patient', 'employee', 'contact']):
            return "Master Data - People/Entities"
        elif any(kw in name_lower for kw in ['product', 'item', 'sku', 'inventory', 'catalog', 'part']):
            return "Master Data - Products/Items"
        elif any(kw in name_lower for kw in ['location', 'store', 'warehouse', 'facility', 'branch']):
            return "Master Data - Locations"
        elif any(kw in name_lower for kw in ['supplier', 'vendor', 'partner', 'agent', 'broker']):
            return "Master Data - Partners"
        
        # Transactional Entities (events, changes over time)
        elif any(kw in name_lower for kw in ['order', 'sale', 'purchase', 'transaction', 'booking']):
            return "Transaction - Sales/Orders"
        elif any(kw in name_lower for kw in ['payment', 'invoice', 'billing', 'revenue', 'premium']):
            return "Transaction - Financial"
        elif any(kw in name_lower for kw in ['claim', 'incident', 'case', 'ticket', 'issue']):
            return "Transaction - Service/Claims"
        elif any(kw in name_lower for kw in ['shipment', 'delivery', 'fulfillment', 'logistics']):
            return "Transaction - Operations"
        
        # Event/Activity Entities
        elif any(kw in name_lower for kw in ['visit', 'session', 'activity', 'interaction', 'event', 'log']):
            return "Event - Activity/Engagement"
        
        # Relationship/Junction Entities
        elif any(kw in name_lower for kw in ['assignment', 'mapping', 'link', 'association']):
            return "Relationship - Junction Table"
        
        # Reference/Lookup Entities
        elif any(kw in name_lower for kw in ['status', 'type', 'category', 'code', 'lookup', 'reference']):
            return "Reference - Lookup/Codes"
        
        # Analyze column patterns if name doesn't match
        has_id_pattern = any('_id' in col or col.endswith('id') for col in columns_lower)
        has_date_pattern = any('date' in col or 'time' in col for col in columns_lower)
        has_amount_pattern = any('amount' in col or 'price' in col or 'value' in col for col in columns_lower)
        
        if has_id_pattern and has_date_pattern and has_amount_pattern:
            return "Transaction - Unknown Type"
        elif has_id_pattern and not has_date_pattern:
            return "Master Data - Unknown Type"
        
        return "Unknown Entity Type"
    
    def _ask_llm_business_questions(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Ask LLM to validate business completeness."""
        
        if not self.llm.llm:
            return self._get_fallback_insights()
        
        prompt = self._build_business_validation_prompt(context)
        
        try:
            # Use LangChain LLM from llm_reasoner
            response = self.llm.llm.invoke(prompt)
            
            # Parse JSON response
            import json
            insights = json.loads(response.content)
            
            logger.success("✓ Business context validated")
            return insights
            
        except Exception as e:
            logger.warning(f"Business validation failed: {e}")
            return self._get_fallback_insights()
    
    def _build_business_validation_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for comprehensive business context validation."""
        
        files_desc = "\n".join([
            f"- **{name}** ({data['entity_type']}): {data['row_count']} rows, "
            f"Keys: {', '.join(data['key_columns']) if data['key_columns'] else 'None'}\n"
            f"  Columns: {', '.join(data['all_columns'][:10])}{'...' if len(data['all_columns']) > 10 else ''}"
            for name, data in context["files"].items()
        ])
        
        relationships_desc = "\n".join([
            f"- {rel['from']} → {rel['to']} (Type: {rel['type']}, Confidence: {rel['confidence']})"
            for rel in context["relationships"]
        ])
        
        prompt = f"""You are an expert business intelligence analyst who evaluates data relationships across any business domain.

DISCOVERED DATA FILES:
{files_desc}

DISCOVERED RELATIONSHIPS:
{relationships_desc}

YOUR TASK: Analyze these discovered relationships and answer the following CRITICAL QUESTIONS:

1. **RELATIONSHIP VALIDITY**: Are these discovered joins logically valid and meaningful?
   - Do the relationships make business sense, or are they just technical column matches?
   - Are there any questionable or unlikely relationships that should be flagged?

2. **BUSINESS STORY**: What type of story does this connected data tell?
   - Classify the data story (e.g., "Customer Journey", "Supply Chain", "Financial Operations", "Service Lifecycle")
   - Explain how the pieces fit together into a coherent narrative

3. **DECISION-MAKING VALUE**: Can decision-makers act on this information?
   - What specific actions can executives/managers take with this connected data?
   - Is the data comprehensive enough to support critical business decisions?
   - What are the data quality concerns that might limit trust?

4. **COHERENCE ANALYSIS**: Are we connecting scattered pieces into a coherent business view?
   - How well do the different data sources integrate?
   - Rate the coherence: Do the relationships create a unified view or remain fragmented?
   - What gaps prevent complete coherence?

5. **CRITICAL INSIGHTS**: What critical insights are revealed by these relationships?
   - What can we now understand that we couldn't from individual files?
   - What patterns, trends, or anomalies become visible?

6. **RELATIONSHIP HELPFULNESS**: For each relationship, is it genuinely helpful or just technically possible?
   - Assess each discovered relationship's value (ESSENTIAL, HELPFUL, MARGINAL, QUESTIONABLE)
   - Explain why each relationship matters (or doesn't)

7. **ANSWERABLE vs UNANSWERABLE**: What questions CAN and CANNOT be answered?
   - List 5-10 specific business questions that CAN be answered with these joins
   - List 3-5 important questions that CANNOT be answered (missing data)

8. **COMPLETENESS**: Do we have a complete picture or are critical pieces missing?
   - Score completeness 0-100
   - Identify what's missing for a complete business view

Respond ONLY with valid JSON (no markdown, no code blocks):

{{
  "completeness_score": 85,
  "coherence_score": 90,
  "tells_complete_story": true,
  "data_story_type": "Customer Lifecycle Analysis",
  "complete_story_explanation": "Brief explanation of the business narrative",
  
  "relationship_validity": {{
    "all_joins_valid": true,
    "validity_explanation": "Explanation of why joins make business sense",
    "questionable_relationships": []
  }},
  
  "decision_making_assessment": {{
    "can_decision_makers_act": true,
    "specific_actions_enabled": [
      "Specific action 1",
      "Specific action 2"
    ],
    "data_quality_concerns": []
  }},
  
  "scattered_pieces_analysis": {{
    "pieces_well_connected": true,
    "coherence_explanation": "How the data sources integrate",
    "gaps_in_coherence": []
  }},
  
  "critical_insights_revealed": [
    "Insight 1",
    "Insight 2",
    "Insight 3"
  ],
  
  "relationship_helpfulness": [
    {{
      "relationship": "file1.col → file2.col",
      "helpfulness": "ESSENTIAL",
      "reason": "Why this relationship is valuable"
    }}
  ],
  
  "missing_critical_pieces": ["entity1", "entity2"],
  
  "answerable_questions": [
    "Question 1",
    "Question 2"
  ],
  
  "unanswerable_questions": [
    "Question 1",
    "Question 2"
  ],
  
  "business_value_assessment": "HIGH",
  "executive_summary": "One-sentence summary of what this connected data enables",
  
  "recommendations": [
    "Recommendation 1",
    "Recommendation 2"
  ]
}}"""
        
        return prompt
    
    def _build_single_relationship_context(
        self,
        relationship: Any,
        source_profile: Dict[str, Any],
        target_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build context for a single relationship analysis."""
        from pathlib import Path
        
        # Get source column profile
        source_col_profile = source_profile["columns"].get(relationship.source_column, {})
        target_col_profile = target_profile["columns"].get(relationship.target_column, {})
        
        # Infer entity types
        source_entity = self._infer_business_entity(
            Path(relationship.source_file).stem, 
            source_profile
        )
        target_entity = self._infer_business_entity(
            Path(relationship.target_file).stem,
            target_profile
        )
        
        return {
            "relationship_id": relationship.relationship_id,
            "source": {
                "file": Path(relationship.source_file).stem,
                "column": relationship.source_column,
                "entity_type": source_entity,
                "data_type": source_col_profile.get("data_type"),
                "sample_values": source_col_profile.get("sample_values", []),
                "uniqueness": source_col_profile.get("unique_percent", 0),
                "is_primary_key": source_col_profile.get("key_features", {}).get("primary_key_candidate", False),
                "row_count": source_profile["row_count"]
            },
            "target": {
                "file": Path(relationship.target_file).stem,
                "column": relationship.target_column,
                "entity_type": target_entity,
                "data_type": target_col_profile.get("data_type"),
                "sample_values": target_col_profile.get("sample_values", []),
                "uniqueness": target_col_profile.get("unique_percent", 0),
                "is_primary_key": target_col_profile.get("key_features", {}).get("primary_key_candidate", False),
                "row_count": target_profile["row_count"]
            },
            "relationship_type": relationship.relationship_type,
            "statistics": relationship.statistics,
            "confidence": relationship.confidence_level
        }
    
    def _ask_llm_single_relationship(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Ask LLM to analyze a single relationship."""
        
        if not self.llm.llm:
            return self._get_fallback_single_relationship_insights()
        
        prompt = self._build_single_relationship_prompt(context)
        
        try:
            response = self.llm.llm.invoke(prompt)
            
            # Parse JSON response
            import json
            insights = json.loads(response.content)
            
            return insights
            
        except Exception as e:
            logger.warning(f"Single relationship validation failed: {e}")
            return self._get_fallback_single_relationship_insights()
    
    def _build_single_relationship_prompt(self, context: Dict[str, Any]) -> str:
        """Build LLM prompt for single relationship analysis."""
        
        source = context["source"]
        target = context["target"]
        stats = context["statistics"]
        
        prompt = f"""You are an expert business intelligence analyst evaluating a specific data relationship.

RELATIONSHIP TO ANALYZE:

**Source Table:**
- File: {source['file']} ({source['entity_type']})
- Column: {source['column']}
- Data Type: {source['data_type']}
- Sample Values: {', '.join(map(str, source['sample_values'][:5]))}
- Uniqueness: {source['uniqueness']:.1f}%
- {'✓ Primary Key Candidate' if source['is_primary_key'] else ''}
- Row Count: {source['row_count']:,}

**Target Table:**
- File: {target['file']} ({target['entity_type']})
- Column: {target['column']}
- Data Type: {target['data_type']}
- Sample Values: {', '.join(map(str, target['sample_values'][:5]))}
- Uniqueness: {target['uniqueness']:.1f}%
- {'✓ Primary Key Candidate' if target['is_primary_key'] else ''}
- Row Count: {target['row_count']:,}

**Relationship Details:**
- Type: {context['relationship_type']}
- Confidence: {context['confidence']}
- Value Overlap: {stats.get('value_overlap_percent', 0):.1f}%
- Orphan Records (Source): {stats.get('orphans_in_source', 0)}
- Orphan Records (Target): {stats.get('orphans_in_target', 0)}

ANALYZE THIS SPECIFIC RELATIONSHIP ONLY:

1. **VALIDITY**: Is this join logically valid and meaningful for business analysis?
2. **STORY**: What specific story does connecting THESE TWO tables tell?
3. **DECISION VALUE**: What specific decisions can be made with THIS connection?
4. **INSIGHTS**: What insights are revealed by joining these specific tables?
5. **HELPFULNESS**: Is this relationship ESSENTIAL, HELPFUL, MARGINAL, or QUESTIONABLE?
6. **ANSWERABLE QUESTIONS**: What specific questions become answerable with THIS join?
7. **DATA QUALITY**: Any concerns about this specific connection?

Respond ONLY with valid JSON (no markdown, no code blocks):

{{
  "relationship_validity": {{
    "is_valid": true,
    "explanation": "Brief explanation of why this join makes business sense"
  }},
  "what_story_it_tells": "One sentence describing what connecting these tables reveals",
  "decision_making_value": {{
    "can_decision_makers_act": true,
    "specific_actions_enabled": [
      "Specific action 1",
      "Specific action 2"
    ]
  }},
  "critical_insights_revealed": [
    "Insight 1 from this join",
    "Insight 2 from this join"
  ],
  "answerable_questions": [
    "Question 1 answerable with this join",
    "Question 2 answerable with this join"
  ],
  "is_relationship_helpful": "ESSENTIAL",
  "helpfulness_reason": "Why this specific relationship is valuable",
  "data_quality_concerns": []
}}"""
        
        return prompt
    
    def _get_fallback_single_relationship_insights(self) -> Dict[str, Any]:
        """Return fallback insights for a single relationship when LLM is unavailable."""
        return {
            "relationship_validity": {
                "is_valid": None,
                "explanation": "LLM validation required"
            },
            "what_story_it_tells": "LLM validation unavailable",
            "decision_making_value": {
                "can_decision_makers_act": None,
                "specific_actions_enabled": []
            },
            "critical_insights_revealed": [],
            "answerable_questions": [],
            "is_relationship_helpful": "UNKNOWN",
            "helpfulness_reason": "LLM validation required",
            "data_quality_concerns": ["LLM validation unavailable"]
        }
    
    def _get_fallback_insights(self) -> Dict[str, Any]:
        """Return basic insights when LLM is unavailable."""
        return {
            "completeness_score": 0,
            "coherence_score": 0,
            "tells_complete_story": False,
            "data_story_type": "UNKNOWN",
            "complete_story_explanation": "LLM validation unavailable - unable to assess business context",
            "relationship_validity": {
                "all_joins_valid": None,
                "validity_explanation": "LLM validation required",
                "questionable_relationships": []
            },
            "decision_making_assessment": {
                "can_decision_makers_act": None,
                "specific_actions_enabled": [],
                "data_quality_concerns": ["LLM validation unavailable"]
            },
            "scattered_pieces_analysis": {
                "pieces_well_connected": None,
                "coherence_explanation": "LLM validation required",
                "gaps_in_coherence": []
            },
            "critical_insights_revealed": [],
            "relationship_helpfulness": [],
            "missing_critical_pieces": [],
            "answerable_questions": [],
            "unanswerable_questions": [],
            "business_value_assessment": "UNKNOWN",
            "executive_summary": "Technical relationships detected, but business context not validated",
            "recommendations": ["Enable LLM validation for comprehensive business context analysis"]
        }
