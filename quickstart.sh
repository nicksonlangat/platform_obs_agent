#!/bin/bash

# Platform Observability Agent - Quick Start
# This script helps customers get started quickly

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE} Platform Observability Agent  ${NC}"
echo -e "${BLUE}       Quick Start Guide       ${NC}"
echo -e "${BLUE}================================${NC}"
echo

# Check if config file exists
if [[ ! -f "agent_config.json" ]]; then
    echo -e "${YELLOW}Creating configuration file from template...${NC}"

    if [[ -f "agent_config.json.example" ]]; then
        cp agent_config.json.example agent_config.json
        echo -e "${GREEN}✓${NC} Configuration file created: agent_config.json"
        echo
        echo -e "${YELLOW}⚠ IMPORTANT: Edit agent_config.json with your details before continuing!${NC}"
        echo
        echo "Required changes:"
        echo "1. Update 'api_endpoint' with your platform URL"
        echo "2. Update 'api_token' with your API token from the dashboard"
        echo "3. Update 'log_source_id' with your log source UUID"
        echo "4. Update 'log_files' with paths to your actual log files"
        echo
        echo "Example configuration:"
        echo '{'
        echo '  "api_endpoint": "https://your-platform.com/api",'
        echo '  "api_token": "pos_abc123...",'
        echo '  "log_source_id": "uuid-here",'
        echo '  "log_files": ["/var/log/nginx/access.log"]'
        echo '}'
        echo
        read -p "Press Enter after editing the configuration file..."
    else
        echo -e "${RED}✗${NC} Template file not found. Please create agent_config.json manually."
        exit 1
    fi
fi

# Test configuration
echo -e "${BLUE}Testing configuration...${NC}"
if python3 agent.py --test-config; then
    echo -e "${GREEN}✓ Configuration test passed!${NC}"
else
    echo -e "${RED}✗ Configuration test failed. Please check your settings.${NC}"
    exit 1
fi

echo
echo -e "${BLUE}Ready to install!${NC}"
echo
echo "The installer will:"
echo "• Install Python dependencies"
echo "• Set up the agent as a system service"
echo "• Configure automatic startup"
echo "• Set up log rotation"
echo
read -p "Continue with installation? (y/N): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}Starting installation...${NC}"
    echo
    sudo ./install.sh
else
    echo "Installation cancelled."
    echo
    echo "To install later, run: sudo ./install.sh"
fi