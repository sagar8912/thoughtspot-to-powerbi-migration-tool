"""
Demo Data Generator for Excel Relationship Discovery System
Creates realistic FNOL call center analytics datasets that demonstrate all 30+ relationship detection cases.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
from pathlib import Path

# Set random seed for reproducibility
np.random.seed(42)
random.seed(42)

# Create output directory
OUTPUT_DIR = Path("demo_data")
OUTPUT_DIR.mkdir(exist_ok=True)

# ============================================================================
# MASTER DATA GENERATION
# ============================================================================

def generate_agents_master():
    """
    FILE 1: Agents Master Data
    Demonstrates: Primary Key detection, Natural Keys, Sequential IDs
    """
    agents = []
    
    agent_names = [
        "Sarah Johnson", "Michael Chen", "Emily Rodriguez", "David Park",
        "Jessica Williams", "Robert Kim", "Amanda Lopez", "James Taylor",
        "Maria Garcia", "Christopher Lee"
    ]
    
    team_leads = ["Alice Manager", "Bob Supervisor", "Carol Director"]
    
    for i, name in enumerate(agent_names, start=1):
        agents.append({
            "AgentID": i,  # Sequential ID (Surrogate Key)
            "Agent_Code": f"AGT{i:04d}",  # Natural Key with prefix
            "AgentName": name,
            "agent_name": name,  # Duplicate column with different case (for name variation testing)
            "TeamLead": random.choice(team_leads),
            "HireDate": (datetime(2020, 1, 1) + timedelta(days=random.randint(0, 1200))).strftime("%Y-%m-%d"),
            "Status": random.choice(["Active", "Active", "Active", "On Leave"]),
            "EmailAddress": f"{name.lower().replace(' ', '.')}@fnol.com",
            "WorkLocation": random.choice(["Remote", "Office A", "Office B"])
        })
    
    return pd.DataFrame(agents)


def generate_performance_data():
    """
    FILE 2: Agent Performance Metrics
    Demonstrates: FK relationships, Abbreviations, Format mismatches
    """
    performance = []
    
    months = ["2023-01", "2023-02", "2023-03", "2023-04", "2023-05", "2023-06"]
    
    for agent_id in range(1, 11):
        for month in months:
            year, month_num = month.split("-")
            performance.append({
                "perf_id": len(performance) + 1,  # Auto-increment
                "agt_code": f"AGT{agent_id:04d}",  # Matches Agent_Code but abbreviated column name
                "AgentID": agent_id,  # Direct FK match
                "reporting_month": month,
                "year": int(year),
                "month": int(month_num),
                "calls_handled": random.randint(150, 500),
                "avg_handle_time_sec": random.randint(180, 600),
                "customer_satisfaction": round(random.uniform(7.5, 9.8), 2),
                "performance_score": random.randint(65, 98),
                "Score": random.randint(65, 98),  # Duplicate for semantic matching
                "first_call_resolution_pct": round(random.uniform(0.75, 0.95), 2)
            })
    
    return pd.DataFrame(performance)


def generate_mistake_tracking():
    """
    FILE 3: Mistake Analysis
    Demonstrates: Composite keys, Pattern matching, Case sensitivity
    """
    mistakes = []
    
    mistake_types = [
        "Incorrect Policy Lookup",
        "Missing Documentation",
        "Wrong Coverage Determination",
        "Compliance Violation",
        "Data Entry Error"
    ]
    
    root_causes = [
        "Lack of Training",
        "System Issue",
        "Communication Gap",
        "Process Complexity"
    ]
    
    for i in range(100):
        agent_id = random.randint(1, 10)
        mistakes.append({
            "mistake_id": f"MST-{i+1:05d}",  # Format with prefix
            "MistakeID": i + 1,  # Same data, different format (for format mismatch testing)
            "agent_identifier": agent_id,  # FK with different name
            "mistake_type": random.choice(mistake_types),
            "MistakeType": random.choice(mistake_types).upper(),  # Case mismatch
            "severity": random.choice(["Low", "Medium", "High", "Critical"]),
            "date_occurred": (datetime(2023, 1, 1) + timedelta(days=random.randint(0, 180))).strftime("%Y-%m-%d"),
            "root_cause": random.choice(root_causes),
            "corrective_action": random.choice(["Training Provided", "System Updated", "SOP Revised"]),
            "repeat_mistake": random.choice([True, False, False, False])
        })
    
    return pd.DataFrame(mistakes)


def generate_sop_compliance():
    """
    FILE 4: SOP Deviation Tracking
    Demonstrates: Fuzzy matching, Transformation needed, Orphan detection
    """
    sop_steps = [
        "Verify Caller Identity",
        "Confirm Policy Status",
        "Document Incident Details",
        "Assign Claim Number",
        "Send Confirmation Email"
    ]
    
    deviations = []
    
    for i in range(80):
        agent_id = random.randint(1, 12)  # Intentionally includes agent_id 11, 12 (orphans)
        deviations.append({
            "deviation_id": i + 1,
            "AGENT_CODE": f"agt{agent_id:04d}",  # Case mismatch + format variation
            "call_id": f"CALL{i+1000:06d}",
            "sop_step_missed": random.choice(sop_steps),
            "criticality": random.choice(["Low", "Medium", "High"]),
            "deviation_date": (datetime(2023, 1, 1) + timedelta(days=random.randint(0, 180))).strftime("%m/%d/%Y"),  # Different date format
            "business_impact": random.choice(["None", "Minor Delay", "Customer Complaint", "Regulatory Risk"]),
            "was_caught_in_qa": random.choice([True, True, False])
        })
    
    return pd.DataFrame(deviations)


def generate_call_volume():
    """
    FILE 5: Call Volume Metrics
    Demonstrates: Aggregated data, Time-based relationships, NULL handling
    """
    call_volume = []
    
    for agent_id in range(1, 11):
        for week_num in range(1, 25):
            # Intentionally leave some NULL values for testing
            calls = random.randint(30, 120) if random.random() > 0.1 else None
            
            call_volume.append({
                "record_id": len(call_volume) + 1,
                "Agent_ID": agent_id,  # Different casing
                "agent_ref": f"AGT{agent_id:04d}",  # Alternative FK
                "week_number": week_num,
                "year": 2023,
                "total_calls": calls,
                "inbound_calls": int(calls * 0.7) if calls else None,
                "outbound_calls": int(calls * 0.3) if calls else None,
                "avg_wait_time": random.randint(30, 300) if calls else None,
                "abandoned_calls": random.randint(0, 10) if calls else None
            })
    
    return pd.DataFrame(call_volume)


def generate_training_records():
    """
    FILE 6: Training & Certifications
    Demonstrates: Many-to-many relationships, Date handling
    """
    training_programs = [
        "FNOL Basics",
        "Advanced Claims",
        "Compliance & Regulations",
        "Customer Service Excellence",
        "System Training"
    ]
    
    trainings = []
    
    for agent_id in range(1, 11):
        # Each agent takes 2-4 trainings
        num_trainings = random.randint(2, 4)
        selected_programs = random.sample(training_programs, num_trainings)
        
        for program in selected_programs:
            trainings.append({
                "training_id": len(trainings) + 1,
                "emp_id": agent_id,  # FK with abbreviated name
                "training_program": program,
                "completion_dt": (datetime(2022, 1, 1) + timedelta(days=random.randint(0, 730))).strftime("%Y-%m-%d"),
                "score_pct": round(random.uniform(0.70, 1.00), 2),
                "certification_status": random.choice(["Certified", "Certified", "Expired"]),
                "expires_on": (datetime(2024, 1, 1) + timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d")
            })
    
    return pd.DataFrame(trainings)


# ============================================================================
# GENERATE ALL FILES
# ============================================================================

def main():
    print("=" * 60)
    print("Generating Demo FNOL Analytics Dataset")
    print("=" * 60)
    
    # Generate all datasets
    datasets = {
        "01_Agents_Master.xlsx": generate_agents_master(),
        "02_Performance_Metrics.xlsx": generate_performance_data(),
        "03_Mistake_Analysis.xlsx": generate_mistake_tracking(),
        "04_SOP_Deviations.xlsx": generate_sop_compliance(),
        "05_Call_Volume.xlsx": generate_call_volume(),
        "06_Training_Records.xlsx": generate_training_records()
    }
    
    # Save to Excel files
    for filename, df in datasets.items():
        filepath = OUTPUT_DIR / filename
        df.to_excel(filepath, index=False)
        print(f"✓ Created {filename}: {len(df)} rows, {len(df.columns)} columns")
    
    print("\n" + "=" * 60)
    print("Demo files created successfully!")
    print(f"Location: {OUTPUT_DIR.absolute()}")
    print("=" * 60)
    
    # Print relationship map
    print("\n📊 Expected Relationship Detections:\n")
    print("HIGH CONFIDENCE:")
    print("  • Agents_Master.AgentID ↔ Performance_Metrics.AgentID (Exact Match)")
    print("  • Agents_Master.Agent_Code ↔ Performance_Metrics.agt_code (Name Variation)")
    print()
    print("MEDIUM CONFIDENCE:")
    print("  • Agents_Master.AgentID ↔ Mistake_Analysis.agent_identifier (Semantic)")
    print("  • Agents_Master.Agent_Code ↔ SOP_Deviations.AGENT_CODE (Case + Format Mismatch)")
    print("  • Performance_Metrics.performance_score ↔ Performance_Metrics.Score (Duplicate)")
    print()
    print("DATA QUALITY ISSUES TO DETECT:")
    print("  • SOP_Deviations has orphan records (Agent 11, 12 don't exist)")
    print("  • Call_Volume has NULL values (10% missing)")
    print("  • Mistake_Analysis.MistakeType has case inconsistencies")
    print()


if __name__ == "__main__":
    main()
