#!/bin/sh
# A simple script to generate data to be reviewed for the test suite.

for i in default dev extras marker source extras_marker; do
    pushd "data/requirements/${i}/"

    python3 ../../../../micropipenv.py requirements --no-hashes > requirements_no_hashes.txt
    python3 ../../../../micropipenv.py requirements --no-indexes > requirements_no_indexes.txt
    python3 ../../../../micropipenv.py requirements --no-versions > requirements_no_versions.txt
    python3 ../../../../micropipenv.py requirements --only-direct > requirements_only_direct.txt
    python3 ../../../../micropipenv.py requirements --no-comments > requirements_no_comments.txt
    python3 ../../../../micropipenv.py requirements --no-default > requirements_no_default.txt
    python3 ../../../../micropipenv.py requirements --no-dev > requirements_no_dev.txt

    popd
done
