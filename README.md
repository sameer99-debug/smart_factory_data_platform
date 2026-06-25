# Smart Factory Data Platform

## Project Summary
This project simulates a manufacturing factory and builds an analytics platform using Python, PostgreSQL and Power BI.

## Current Version
Version 1 covers:
- Synthetic factory data generation
- PostgreSQL staging, cleaning, and mart layers
- Data quality checks
- Power BI dashboard for OEE, downtime, scrap, throughput, and operator performance

## System Requirements
CPU: 4 or more physical cores (recommended for parallel data generation and ingestion)  
RAM: Minimum 8 GB  
Disk Space: At least 5 GB of free storage for generated datasets and the PostgreSQL database  
Operating System: Windows 10/11, Linux, or macOS  
Python: Version 3.11 or later  
PostgreSQL: Version 16 or later  
Power BI Desktop  
Install the required packages using: pip install -r requirements.txt

## Architecture
Python Faker → CSV → PostgreSQL Stage → Clean → Marts → Power BI

## Factory Processes
- Punching
- Bending
- Welding
- Assembly
- Powder Coating
- Packaging

## KPIs
- OEE
- Availability
- Performance
- Quality
- Scrap Rate
- Downtime Minutes
- Throughput

## Next Phase
- Airflow orchestration
- dbt transformations
- Streaming telemetry pipeline
- Dockerized local environment
