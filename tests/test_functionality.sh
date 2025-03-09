#!/bin/bash
# Script to test the functionality of the main script in the virtual environment

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

# Run the functionality test script
echo -e "\nRunning functionality test..."
python test_functionality.py

# Check if the test was successful
if [ $? -eq 0 ]; then
    echo -e "\n✅ Functionality test passed"
else
    echo -e "\n❌ Functionality test failed"
    exit 1
fi

# Deactivate the virtual environment
deactivate
echo -e "\nVirtual environment deactivated"

echo -e "\nAll tests completed successfully" 