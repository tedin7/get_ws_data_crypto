#!/bin/bash
# Test script to verify that the main functionality works with the virtual environment

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

# Check Python version
echo -e "\nPython version:"
python --version

# Check installed packages
echo -e "\nInstalled packages:"
pip list

# Run the test script
echo -e "\nRunning main functionality test..."
python tests/test_main.py

# Check if the test was successful
if [ $? -eq 0 ]; then
    echo -e "\n✅ All tests passed"
else
    echo -e "\n❌ Tests failed"
    exit 1
fi

# Test the actual main script (without actually running it)
echo -e "\nChecking if main.py can be imported without errors..."
python -c "import main; print('✅ main.py can be imported without errors')"

if [ $? -eq 0 ]; then
    echo "✅ main.py is compatible with the virtual environment"
else
    echo "❌ main.py has import errors"
    exit 1
fi

# Deactivate the virtual environment
deactivate
echo -e "\nVirtual environment deactivated"

echo -e "\nAll tests completed successfully" 