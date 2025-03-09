#!/bin/bash
# Simple script to test if the main script can be imported and run in the virtual environment

# Set the working directory
cd "$(dirname "$0")"

# Activate the virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if the virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "❌ Failed to activate virtual environment"
    exit 1
else
    echo "✅ Virtual environment activated: $VIRTUAL_ENV"
fi

# Run the import test script
echo -e "\nRunning import test..."
python test_import.py

# Check if the test was successful
if [ $? -eq 0 ]; then
    echo -e "\n✅ Import test passed"
else
    echo -e "\n❌ Import test failed"
    exit 1
fi

# Deactivate the virtual environment
deactivate
echo -e "\nVirtual environment deactivated"

echo -e "\nAll tests completed successfully" 