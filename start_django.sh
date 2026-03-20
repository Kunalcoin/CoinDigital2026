#!/bin/bash

# Define an array of port numbers for each instance
declare -a ports=("8000" "8001" "8002")

# Define an array of Django project directories for each instance
declare -a projects=("RoyaltyWebsite" "RoyaltyWebsite" "RoyaltyWebsite")

# Iterate over the arrays and start Django instances on different ports
for i in "${!ports[@]}"; do
    port=${ports[i]}
    project=${projects[i]}

    # Change directory to the Django project
    cd "$project"

    # Start the Django instance on the specified port
    python manage.py runserver "$port" &

    # Return to the parent directory
    cd ..
done
