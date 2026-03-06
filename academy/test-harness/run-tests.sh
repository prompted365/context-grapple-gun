#!/usr/bin/env bash
#
# Homeskillet Academy Test Harness
#
# Usage:
#   ./run-tests.sh 1        # Run chapter 1 tests
#   ./run-tests.sh 3        # Run chapter 3 tests
#   ./run-tests.sh all      # Run all chapters
#   ./run-tests.sh status   # Show pass/fail summary
#

set -euo pipefail

# --- Terminal colors (if supported) ---
if [ -t 1 ] && command -v tput &>/dev/null && [ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]; then
    GREEN=$(tput setaf 2)
    RED=$(tput setaf 1)
    YELLOW=$(tput setaf 3)
    CYAN=$(tput setaf 6)
    BOLD=$(tput bold)
    RESET=$(tput sgr0)
else
    GREEN=""
    RED=""
    YELLOW=""
    CYAN=""
    BOLD=""
    RESET=""
fi

# --- Resolve project root ---
# The test harness lives at academy/test-harness/run-tests.sh
# We need to find the academy root (one directory up from test-harness/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACADEMY_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Chapter map ---
declare -A CHAPTER_SLUGS
CHAPTER_SLUGS[1]="01-append-only-truth"
CHAPTER_SLUGS[2]="02-dedup-and-identity"
CHAPTER_SLUGS[3]="03-signals-and-decay"
CHAPTER_SLUGS[4]="04-human-gated-review"
CHAPTER_SLUGS[5]="05-completion"

declare -A CHAPTER_TESTS
CHAPTER_TESTS[1]="test_event_store.py"
CHAPTER_TESTS[2]="test_dedup_scanner.py"
CHAPTER_TESTS[3]="test_signal_manager.py"
CHAPTER_TESTS[4]="test_review_queue.py"
CHAPTER_TESTS[5]="test_completion.py"

declare -A CHAPTER_NAMES
CHAPTER_NAMES[1]="The Taylor Family Calendar"
CHAPTER_NAMES[2]="The Adjunct's Semester Project"
CHAPTER_NAMES[3]="Zookeeper Radio"
CHAPTER_NAMES[4]="Bridge Inspector"
CHAPTER_NAMES[5]="Graduation"

# --- Helpers ---

check_src() {
    if [ ! -d "$ACADEMY_ROOT/src" ]; then
        echo ""
        echo "${YELLOW}The src/ directory doesn't exist yet.${RESET}"
        echo "Create it first:"
        echo ""
        echo "  mkdir -p $ACADEMY_ROOT/src && touch $ACADEMY_ROOT/src/__init__.py"
        echo ""
        exit 1
    fi
}

check_chapter_exists() {
    local num=$1
    local slug="${CHAPTER_SLUGS[$num]:-}"
    local test="${CHAPTER_TESTS[$num]:-}"

    if [ -z "$slug" ]; then
        echo "${RED}Unknown chapter: $num${RESET}"
        echo "Valid chapters: 1, 2, 3, 4, 5"
        exit 1
    fi

    local test_path="$ACADEMY_ROOT/chapters/$slug/$test"
    if [ ! -f "$test_path" ]; then
        echo "${YELLOW}Test file not found: chapters/$slug/$test${RESET}"
        echo "This chapter's tests may not be created yet."
        return 1
    fi
    return 0
}

run_chapter() {
    local num=$1
    local slug="${CHAPTER_SLUGS[$num]}"
    local test="${CHAPTER_TESTS[$num]}"
    local name="${CHAPTER_NAMES[$num]}"
    local test_path="$ACADEMY_ROOT/chapters/$slug/$test"

    echo ""
    echo "${BOLD}${CYAN}Chapter $num: $name${RESET}"
    echo "${CYAN}  $slug/$test${RESET}"
    echo ""

    if [ ! -f "$test_path" ]; then
        echo "  ${YELLOW}SKIP${RESET} -- test file not found"
        return 2
    fi

    if (cd "$ACADEMY_ROOT" && python -m pytest "$test_path" -v --tb=short 2>&1); then
        return 0
    else
        return 1
    fi
}

run_chapter_quiet() {
    local num=$1
    local slug="${CHAPTER_SLUGS[$num]}"
    local test="${CHAPTER_TESTS[$num]}"
    local test_path="$ACADEMY_ROOT/chapters/$slug/$test"

    if [ ! -f "$test_path" ]; then
        echo "skip"
        return
    fi

    if (cd "$ACADEMY_ROOT" && python -m pytest "$test_path" -q --tb=no 2>&1 >/dev/null); then
        echo "pass"
    else
        echo "fail"
    fi
}

# --- Commands ---

cmd_run_one() {
    local num=$1
    check_src
    check_chapter_exists "$num" || exit 1
    run_chapter "$num"
    exit $?
}

cmd_run_all() {
    check_src

    local total=0
    local passed=0
    local failed=0
    local skipped=0

    for num in 1 2 3 4 5; do
        total=$((total + 1))
        if run_chapter "$num"; then
            passed=$((passed + 1))
        else
            local rc=$?
            if [ "$rc" -eq 2 ]; then
                skipped=$((skipped + 1))
            else
                failed=$((failed + 1))
            fi
        fi
    done

    echo ""
    echo "${BOLD}---${RESET}"
    echo "${BOLD}Results:${RESET} ${GREEN}$passed passed${RESET}, ${RED}$failed failed${RESET}, ${YELLOW}$skipped skipped${RESET} / $total total"
    echo ""

    if [ "$failed" -gt 0 ]; then
        exit 1
    fi
    exit 0
}

cmd_status() {
    check_src

    echo ""
    echo "${BOLD}Homeskillet Academy -- Chapter Status${RESET}"
    echo ""
    printf "  %-4s  %-40s  %s\n" "#" "Chapter" "Status"
    printf "  %-4s  %-40s  %s\n" "---" "----------------------------------------" "------"

    local any_fail=0

    for num in 1 2 3 4 5; do
        local name="${CHAPTER_NAMES[$num]}"
        local result
        result=$(run_chapter_quiet "$num")

        case "$result" in
            pass)
                printf "  %-4s  %-40s  ${GREEN}%s${RESET}\n" "$num" "$name" "PASS"
                ;;
            fail)
                printf "  %-4s  %-40s  ${RED}%s${RESET}\n" "$num" "$name" "FAIL"
                any_fail=1
                ;;
            skip)
                printf "  %-4s  %-40s  ${YELLOW}%s${RESET}\n" "$num" "$name" "SKIP"
                ;;
        esac
    done

    echo ""

    if [ "$any_fail" -eq 1 ]; then
        exit 1
    fi
    exit 0
}

# --- Usage ---

usage() {
    echo ""
    echo "${BOLD}Homeskillet Academy Test Harness${RESET}"
    echo ""
    echo "Usage:"
    echo "  ./run-tests.sh <chapter>   Run tests for a specific chapter (1-5)"
    echo "  ./run-tests.sh all         Run all chapter tests sequentially"
    echo "  ./run-tests.sh status      Show pass/fail summary for all chapters"
    echo ""
    echo "Examples:"
    echo "  ./run-tests.sh 1           Run Chapter 1: The Taylor Family Calendar"
    echo "  ./run-tests.sh 3           Run Chapter 3: Zookeeper Radio"
    echo "  ./run-tests.sh all         Run everything"
    echo "  ./run-tests.sh status      Quick pass/fail table"
    echo ""
}

# --- Main ---

if [ $# -eq 0 ]; then
    usage
    exit 0
fi

case "$1" in
    1|2|3|4|5)
        cmd_run_one "$1"
        ;;
    all)
        cmd_run_all
        ;;
    status)
        cmd_status
        ;;
    -h|--help|help)
        usage
        exit 0
        ;;
    *)
        echo "${RED}Unknown argument: $1${RESET}"
        usage
        exit 1
        ;;
esac
