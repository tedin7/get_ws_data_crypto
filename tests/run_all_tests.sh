#!/bin/bash
# Master test script that runs all the tests in sequence

# Set the working directory
cd "$(dirname "$0")"

# Print header
function print_header() {
    echo -e "\n=============================================================="
    echo -e "                   $1"
    echo -e "==============================================================\n"
}

# Run a test and check the result
function run_test() {
    local test_name="$1"
    local test_script="$2"
    
    print_header "$test_name"
    echo "Running $test_script..."
    
    ./$test_script
    
    if [ $? -eq 0 ]; then
        echo -e "\n✅ $test_name passed"
        return 0
    else
        echo -e "\n❌ $test_name failed"
        return 1
    fi
}

# Print the master header
print_header "BYBIT API KEY CHECKER - MASTER TEST SUITE"
echo "Started at: $(date '+%Y-%m-%d %H:%M:%S')"
echo "This test suite will verify all components of the API key checker system."

# Create results array
declare -A results

# Test 1: Import Test
run_test "Import Test" "test_simple.sh"
results["import"]=$?

# Test 2: Functionality Test
run_test "Functionality Test" "test_functionality.sh"
results["functionality"]=$?

# Print summary
print_header "TEST SUMMARY"
echo "Completed at: $(date '+%Y-%m-%d %H:%M:%S')"
echo -e "\nTest Results:"
echo "1. Import Test: $([ ${results["import"]} -eq 0 ] && echo 'PASSED' || echo 'FAILED')"
echo "2. Functionality Test: $([ ${results["functionality"]} -eq 0 ] && echo 'PASSED' || echo 'FAILED')"

# Overall result
if [ ${results["import"]} -eq 0 ] && [ ${results["functionality"]} -eq 0 ]; then
    echo -e "\nOverall Test Result: PASSED"
    echo -e "\nAll tests passed! The API key checker system is working correctly."
    exit 0
else
    echo -e "\nOverall Test Result: FAILED"
    echo -e "\nSome tests failed. Please check the output above for details."
    exit 1
fi 