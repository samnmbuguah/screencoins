#!/bin/bash

# Script to set up and run the FVG Screener
# This script will:
# 1. Create a virtual environment if it doesn't exist
# 2. Install all required dependencies
# 3. Run the FVG screener

# Configuration
VENV_NAME="myenv"
REQUIREMENTS_FILE="requirements.txt"

# Colors for terminal output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Ensure we're in the right directory
cd "$(dirname "$0")"

echo -e "${BLUE}=== FVG Screener Setup and Execution ===${NC}"

# Check if Python is installed
if ! command_exists python3; then
    echo -e "${YELLOW}Python 3 is not installed. Please install Python 3 and try again.${NC}"
    exit 1
fi

# Create requirements.txt if it doesn't exist
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo -e "${YELLOW}Creating $REQUIREMENTS_FILE...${NC}"
    cat > "$REQUIREMENTS_FILE" << EOF
ccxt==3.1.56
pandas==2.0.3
numpy==1.24.3
matplotlib==3.7.2
EOF
    echo -e "${GREEN}Created $REQUIREMENTS_FILE${NC}"
fi

# Check if virtual environment exists
if [ ! -d "$VENV_NAME" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv "$VENV_NAME"
    echo -e "${GREEN}Virtual environment created!${NC}"
fi

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source "$VENV_NAME/bin/activate"

# Check if activation was successful
if [ "$VIRTUAL_ENV" == "" ]; then
    echo -e "${YELLOW}Failed to activate virtual environment. Please check your Python installation.${NC}"
    exit 1
fi

# Install dependencies
echo -e "${BLUE}Installing dependencies...${NC}"
pip install -r "$REQUIREMENTS_FILE"
echo -e "${GREEN}Dependencies installed!${NC}"

# Make sure the results directory exists
mkdir -p screener/results

# Check if we need to extract futures symbols first
if [ ! -f "screener/results/valid_futures_symbols.json" ]; then
    echo -e "${YELLOW}No valid futures symbols found. Running extraction script...${NC}"
    python3 extract_futures_symbols.py
    echo -e "${GREEN}Futures symbols extracted!${NC}"
fi

# Run the screener
echo -e "${BLUE}Running FVG Screener...${NC}"
cd screener
python3 run_fvg_screener.py

echo -e "${GREEN}Screening complete! Results are saved in the screener/results directory.${NC}"
echo -e "${BLUE}Deactivating virtual environment...${NC}"
deactivate

echo -e "${GREEN}Done!${NC}" 