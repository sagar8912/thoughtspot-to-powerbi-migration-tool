"""Model Enhancement Guide Generator - Creates human-readable guides for Power BI model changes"""
from pathlib import Path
from typing import List
from loguru import logger

from src.powerbi.model_enhancement_agent import ModelEnhancement, EnhancementType


class EnhancementGuideGenerator:
    """
    Generate markdown documentation for model enhancements

    Output:
    - MODEL_ENHANCEMENTS_REQUIRED.md - Main guide
    - m_scripts/ folder - Power Query M scripts
    - dax_scripts/ folder - DAX calculated columns
    """

    def generate_guide(
        self,
        enhancements: List[ModelEnhancement],
        output_dir: Path
    ) -> Path:
        """
        Generate comprehensive enhancement guide

        Args:
            enhancements: List of required model enhancements
            output_dir: Directory to write files

        Returns:
            Path to main guide markdown file
        """
        if not enhancements:
            logger.info("No model enhancements required - skipping guide generation")
            return None

        logger.info(f"Generating enhancement guide for {len(enhancements)} enhancements")

        # Create output directories
        output_dir.mkdir(parents=True, exist_ok=True)
        m_scripts_dir = output_dir / "m_scripts"
        dax_scripts_dir = output_dir / "dax_scripts"
        m_scripts_dir.mkdir(exist_ok=True)
        dax_scripts_dir.mkdir(exist_ok=True)

        # Generate main guide
        guide_path = output_dir / "MODEL_ENHANCEMENTS_REQUIRED.md"
        guide_content = self._generate_main_guide(enhancements)
        guide_path.write_text(guide_content, encoding='utf-8')

        # Generate individual script files
        for i, enhancement in enumerate(enhancements, 1):
            # Save M code
            if enhancement.m_code:
                m_file = m_scripts_dir / f"{i:02d}_{enhancement.affected_calculation}_index.m"
                m_file.write_text(enhancement.m_code, encoding='utf-8')

            # Save DAX code
            if enhancement.dax_code:
                dax_file = dax_scripts_dir / f"{i:02d}_{enhancement.affected_calculation}.dax"
                dax_file.write_text(enhancement.dax_code, encoding='utf-8')

        logger.info(f"✅ Generated enhancement guide: {guide_path}")
        logger.info(f"   - M scripts: {m_scripts_dir}")
        logger.info(f"   - DAX scripts: {dax_scripts_dir}")

        return guide_path

    def _generate_main_guide(self, enhancements: List[ModelEnhancement]) -> str:
        """Generate main markdown guide content"""

        # Group by enhancement type
        by_type = {}
        for enhancement in enhancements:
            etype = enhancement.enhancement_type
            if etype not in by_type:
                by_type[etype] = []
            by_type[etype].append(enhancement)

        content = f"""# Power BI Model Enhancements Required

**Migration Date:** {Path.cwd()}
**Total Enhancements:** {len(enhancements)}

---

## 📋 Overview

Some Tableau calculations use **Table Calculations** that operate at the visual layer.
Power BI requires these to be built into the **data model** itself.

This guide provides step-by-step instructions to complete your migration.

### Summary by Type

"""

        # Summary table
        for etype, items in by_type.items():
            icon = self._get_icon(etype)
            content += f"- {icon} **{etype.value}**: {len(items)} calculation(s)\n"

        content += "\n---\n\n"

        # Detailed instructions for each enhancement
        for i, enhancement in enumerate(enhancements, 1):
            content += self._generate_enhancement_section(i, enhancement)

        # Add quick reference
        content += self._generate_quick_reference()

        return content

    def _generate_enhancement_section(self, index: int, enhancement: ModelEnhancement) -> str:
        """Generate section for a single enhancement"""

        icon = self._get_icon(enhancement.enhancement_type)

        section = f"""
## {icon} Enhancement {index}: {enhancement.affected_calculation}

**Type:** {enhancement.enhancement_type.value}
**Table:** {enhancement.table_name}

### Why This Is Needed

{enhancement.reason}

### Step-by-Step Instructions

"""

        # Add numbered manual steps
        for step in enhancement.manual_steps:
            section += f"{step}\n"

        section += "\n"

        # Add M code if available
        if enhancement.m_code:
            section += f"""
### Power Query M Code

Copy and paste this into Power Query Editor:

```m
{enhancement.m_code}
```

"""

        # Add DAX code if available
        if enhancement.dax_code:
            section += f"""
### DAX Code

After adding the index/column above, create this calculated column (or measure):

```dax
{enhancement.dax_code}
```

**Important:** This is a **Calculated Column**, not a Measure! Right-click your table → New Column → paste the DAX above.

"""

        section += "---\n\n"

        return section

    def _generate_quick_reference(self) -> str:
        """Generate quick reference guide"""

        return """
## 🎯 Quick Reference Guide

### How to Add an Index Column in Power Query

1. Open Power BI Desktop
2. Click **Transform Data** (opens Power Query Editor)
3. Select your table in the left panel
4. Click **Add Column** tab → **Index Column** → **From 1**
5. Rename the column to "RowIndex" (or as specified in M code)
6. Click **Close & Apply**

### How to Create a Calculated Column

1. In Power BI Desktop, select your table in the Fields pane
2. Right-click the table → **New Column**
3. Paste the DAX code from above
4. Press Enter
5. The new column appears in your table

### How to Create a Date Table

1. Open Power Query Editor
2. Click **New Source** → **Blank Query**
3. Click **Advanced Editor**
4. Paste the Date table M code
5. Name the query "DateTable"
6. Click **Close & Apply**
7. In Power BI, right-click DateTable → **Mark as Date Table**
8. Create relationship: DateTable[Date] → YourTable[OrderDate]

### Common Issues

**Q: My calculated column shows an error**
A: Make sure you added the Index column FIRST, then create the calculated column. The column must exist before DAX can reference it.

**Q: Running totals are wrong**
A: Ensure you're using the Date table in your visual axes, not the original date column from your fact table.

**Q: LOOKUP still doesn't work**
A: LOOKUP requires a CALCULATED COLUMN, not a Measure. Measures cannot access "previous" or "next" rows.

---

## 📚 Resources

- [Power Query M Reference](https://learn.microsoft.com/en-us/powerquery-m/)
- [DAX Guide](https://dax.guide/)
- [Create Calculated Columns](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-calculated-columns)
- [Date Tables in Power BI](https://learn.microsoft.com/en-us/power-bi/guidance/model-date-tables)

---

**Generated by Tableau-to-Power BI Migration Engine**
"""

    def _get_icon(self, etype: EnhancementType) -> str:
        """Get emoji icon for enhancement type"""
        icons = {
            EnhancementType.INDEX_COLUMN: "🔢",
            EnhancementType.DATE_TABLE: "📅",
            EnhancementType.SORT_COLUMN: "↕️",
            EnhancementType.RELATIONSHIP: "🔗",
            EnhancementType.NONE: "✅"
        }
        return icons.get(etype, "⚙️")
