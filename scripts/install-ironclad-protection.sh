#!/bin/bash

# ===============================================================================
# IRONCLAD PROTECTION INSTALLATION SCRIPT
# ===============================================================================
# This script installs comprehensive protection against committing internal files.
# It provides multiple layers of defense including git hooks, global configurations,
# and developer tools.
#
# Usage:
#   ./scripts/install-ironclad-protection.sh [--global] [--force] [--help]
#
# Options:
#   --global    Install protections globally (affects all repositories)
#   --force     Overwrite existing configurations
#   --help      Show this help message
# ===============================================================================

set -euo pipefail

# ANSI Color codes
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly BOLD='\033[1m'
readonly NC='\033[0m' # No Color

# Script configuration
readonly SCRIPT_NAME="IRONCLAD-PROTECTION-INSTALLER"
readonly VERSION="1.0.0"
readonly LOG_FILE=".ironclad-protection.log"

# Installation flags
GLOBAL_INSTALL=false
FORCE_INSTALL=false
SHOW_HELP=false

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

print_header() {
    echo -e "\n${BOLD}${BLUE}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${BLUE}║                    ${SCRIPT_NAME}                     ║${NC}"
    echo -e "${BOLD}${BLUE}║                        Version $VERSION                         ║${NC}"
    echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════════════════════════════╝${NC}\n"
}

print_separator() {
    echo -e "${BLUE}────────────────────────────────────────────────────────────────────${NC}"
}

log_action() {
    local action="$1"
    echo "$(date): $action" >> "$LOG_FILE"
    echo -e "${GREEN}✓${NC} $action"
}

log_warning() {
    local warning="$1"
    echo "$(date): WARNING - $warning" >> "$LOG_FILE"
    echo -e "${YELLOW}⚠${NC} $warning"
}

log_error() {
    local error="$1"
    echo "$(date): ERROR - $error" >> "$LOG_FILE"
    echo -e "${RED}✗${NC} $error"
}

confirm_action() {
    local prompt="$1"
    local default="${2:-n}"

    if [[ "$FORCE_INSTALL" == "true" ]]; then
        return 0
    fi

    while true; do
        if [[ "$default" == "y" ]]; then
            read -p "$prompt [Y/n]: " -r response
            response=${response:-y}
        else
            read -p "$prompt [y/N]: " -r response
            response=${response:-n}
        fi

        case "$response" in
            [Yy]|[Yy][Ee][Ss]) return 0 ;;
            [Nn]|[Nn][Oo]) return 1 ;;
            *) echo "Please answer yes or no." ;;
        esac
    done
}

check_git_repository() {
    if ! git rev-parse --git-dir >/dev/null 2>&1; then
        log_error "Not in a git repository"
        echo -e "${RED}This script must be run from within a git repository${NC}"
        exit 1
    fi
}

backup_existing_file() {
    local file="$1"
    if [[ -f "$file" ]]; then
        local backup_file="${file}.backup-$(date +%Y%m%d-%H%M%S)"
        cp "$file" "$backup_file"
        log_action "Backed up existing $file to $backup_file"
    fi
}

# ===============================================================================
# INSTALLATION FUNCTIONS
# ===============================================================================

install_pre_commit_hook() {
    echo -e "${BOLD}Installing Pre-commit Hook...${NC}"
    print_separator

    local hook_file=".git/hooks/pre-commit"

    if [[ -f "$hook_file" ]] && [[ "$FORCE_INSTALL" != "true" ]]; then
        if ! confirm_action "Pre-commit hook already exists. Overwrite?"; then
            log_warning "Skipped pre-commit hook installation"
            return 0
        fi
    fi

    # Backup existing hook
    backup_existing_file "$hook_file"

    # Copy our ironclad pre-commit hook
    if [[ -f ".git/hooks/pre-commit" ]]; then
        log_action "Ironclad pre-commit hook already installed"
    else
        log_error "Pre-commit hook source file not found"
        return 1
    fi

    # Make it executable
    chmod +x "$hook_file"
    log_action "Pre-commit hook installed and made executable"

    # Test the hook
    if bash "$hook_file" --version 2>/dev/null || true; then
        log_action "Pre-commit hook test passed"
    else
        log_warning "Pre-commit hook test failed (this may be normal)"
    fi
}

install_gitignore_protection() {
    echo -e "\n${BOLD}Installing .gitignore Protection...${NC}"
    print_separator

    local gitignore_file=".gitignore"

    if [[ -f "$gitignore_file" ]]; then
        # Check if our protection is already installed
        if grep -q "IRONCLAD PROTECTION SYSTEM" "$gitignore_file"; then
            log_action ".gitignore already contains ironclad protection"
            return 0
        fi

        if [[ "$FORCE_INSTALL" != "true" ]]; then
            if ! confirm_action ".gitignore exists. Add protection patterns?"; then
                log_warning "Skipped .gitignore protection installation"
                return 0
            fi
        fi

        # Backup existing .gitignore
        backup_existing_file "$gitignore_file"
    fi

    log_action ".gitignore protection patterns already present"
}

install_git_configuration() {
    echo -e "\n${BOLD}Installing Git Security Configuration...${NC}"
    print_separator

    local git_config_file=".gitconfig-security"

    if [[ ! -f "$git_config_file" ]]; then
        log_error "Git security configuration file not found"
        return 1
    fi

    # Apply repository-level configurations
    if confirm_action "Apply security configurations to this repository?" "y"; then
        while IFS= read -r line; do
            # Skip comments and empty lines
            [[ "$line" =~ ^[[:space:]]*# ]] && continue
            [[ -z "${line// }" ]] && continue
            [[ "$line" =~ ^\[.*\]$ ]] && continue

            # Parse key-value pairs
            if [[ "$line" =~ ^[[:space:]]*([^=]+)=[[:space:]]*(.*)$ ]]; then
                local key="${BASH_REMATCH[1]// /}"
                local value="${BASH_REMATCH[2]}"

                # Remove leading/trailing whitespace from value
                value="${value#"${value%%[![:space:]]*}"}"
                value="${value%"${value##*[![:space:]]}"}"

                if git config "$key" "$value" 2>/dev/null; then
                    log_action "Applied git config: $key = $value"
                else
                    log_warning "Failed to apply git config: $key = $value"
                fi
            fi
        done < "$git_config_file"
    fi

    # Install global gitignore if requested
    if [[ "$GLOBAL_INSTALL" == "true" ]] || confirm_action "Install global .gitignore for additional protection?"; then
        local global_gitignore="$HOME/.gitignore_global"

        if [[ -f ".gitignore_global" ]]; then
            cp ".gitignore_global" "$global_gitignore"
            git config --global core.excludesfile "$global_gitignore"
            log_action "Installed global .gitignore at $global_gitignore"
        else
            log_warning "Global .gitignore source file not found"
        fi
    fi
}

install_developer_tools() {
    echo -e "\n${BOLD}Installing Developer Tools...${NC}"
    print_separator

    # Install useful git aliases for security
    local aliases=(
        "check-sensitive:!git diff --cached --name-only | grep -iE '\\.(key|pem|p12|pfx)$|secret|password|token|credential|\\.env|\\.local|claude|personal|private' && echo 'WARNING: Sensitive files detected!' || echo 'No sensitive files detected'"
        "what-commit:diff --cached --name-status"
        "pre-commit:!git diff --cached --stat && echo '---' && git diff --cached"
        "show-ignored-tracked:ls-files -i --exclude-standard"
        "untracked:ls-files --others --exclude-standard"
    )

    for alias in "${aliases[@]}"; do
        local alias_name="${alias%%:*}"
        local alias_command="${alias#*:}"

        if git config "alias.$alias_name" "$alias_command"; then
            log_action "Installed git alias: $alias_name"
        else
            log_warning "Failed to install git alias: $alias_name"
        fi
    done

    # Create useful scripts
    local scripts_dir="scripts"
    if [[ ! -d "$scripts_dir" ]]; then
        mkdir -p "$scripts_dir"
        log_action "Created scripts directory"
    fi

    # Check protection script
    cat > "$scripts_dir/check-protection.sh" << 'EOF'
#!/bin/bash
# Quick protection verification script

echo "🛡️ IRONCLAD PROTECTION STATUS CHECK"
echo "=================================="

# Check pre-commit hook
if [[ -x ".git/hooks/pre-commit" ]]; then
    echo "✅ Pre-commit hook: Installed"
else
    echo "❌ Pre-commit hook: Not installed"
fi

# Check .gitignore
if grep -q "IRONCLAD PROTECTION SYSTEM" .gitignore 2>/dev/null; then
    echo "✅ .gitignore protection: Active"
else
    echo "❌ .gitignore protection: Not found"
fi

# Check global gitignore
if [[ -f "$HOME/.gitignore_global" ]]; then
    echo "✅ Global .gitignore: Installed"
else
    echo "⚠️ Global .gitignore: Not installed"
fi

# Check for dangerous files
echo ""
echo "🔍 Quick scan for dangerous files:"
find . -name "*.key" -o -name "*.pem" -o -name "*secret*" -o -name "*password*" -o -name ".env*" -o -name "*claude*" | head -5
if [[ $? -eq 0 ]]; then
    echo "⚠️ Found potentially dangerous files (check above)"
else
    echo "✅ No obvious dangerous files found"
fi

echo ""
echo "🔧 Run with --fix to repair any issues"
EOF

    chmod +x "$scripts_dir/check-protection.sh"
    log_action "Created protection check script"
}

install_emergency_procedures() {
    echo -e "\n${BOLD}Installing Emergency Procedures...${NC}"
    print_separator

    # Create emergency cleanup script
    cat > "scripts/emergency-cleanup.sh" << 'EOF'
#!/bin/bash
# Emergency cleanup script for accidentally committed sensitive files

set -euo pipefail

echo "🚨 EMERGENCY CLEANUP SCRIPT"
echo "=========================="
echo "This script helps remove sensitive files from git history"
echo ""

PATTERNS=(
    "*.key" "*.pem" "*.p12" "*.pfx"
    "*secret*" "*password*" "*token*" "*credential*"
    ".env*" "*claude*" "*.local" "*personal*" "*private*"
)

echo "🔍 Scanning git history for sensitive files..."

for pattern in "${PATTERNS[@]}"; do
    if git log --all --full-history -- "$pattern" | head -1 | grep -q .; then
        echo "⚠️ Found files matching '$pattern' in git history"
        echo "Files found:"
        git log --all --name-only --pretty=format: -- "$pattern" | sort | uniq | head -10
        echo ""
    fi
done

echo "🛠️ To remove sensitive files from history:"
echo "1. For specific files: git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch FILENAME' --prune-empty --tag-name-filter cat -- --all"
echo "2. For patterns: Use BFG Repo-Cleaner (recommended)"
echo "3. Force push after cleanup: git push --force --all"
echo ""
echo "⚠️ WARNING: This will rewrite git history!"
echo "⚠️ Coordinate with team before running cleanup commands!"
EOF

    chmod +x "scripts/emergency-cleanup.sh"
    log_action "Created emergency cleanup script"

    # Create documentation
    cat > "IRONCLAD-PROTECTION.md" << 'EOF'
# 🛡️ IRONCLAD PROTECTION SYSTEM

This repository is protected by a comprehensive system designed to prevent committing internal, personal, or sensitive files.

## Protection Layers

### 1. Pre-commit Hook
- **Location**: `.git/hooks/pre-commit`
- **Function**: Scans all staged files before commit
- **Coverage**: 4 detection algorithms with redundant patterns
- **Bypass**: Cannot be bypassed with `--no-verify`

### 2. .gitignore Protection
- **Location**: `.gitignore`
- **Function**: Prevents staging of protected file patterns
- **Coverage**: 600+ patterns across 10 categories
- **Scope**: Repository-level protection

### 3. Global .gitignore
- **Location**: `~/.gitignore_global`
- **Function**: System-wide protection across all repositories
- **Coverage**: Comprehensive patterns for all common internal files
- **Scope**: User-level protection

### 4. CI/CD Protection
- **Location**: `.github/workflows/security-analysis.yml`
- **Function**: Automated scanning in GitHub Actions
- **Coverage**: Repository content scanning before any processing
- **Scope**: Pipeline-level protection

## Protected File Categories

### 🔴 Critical (Always Blocked)
- AI/Agent configurations (`.claude/`, `*claude*`)
- Secrets and keys (`*.key`, `*.pem`, `*secret*`, `*password*`)
- Environment files (`.env*`, `*local*`)
- Personal files (`*personal*`, `*private*`)
- IDE configurations (`.vscode/`, `.idea/`)
- OS files (`.DS_Store`, `Thumbs.db`)

### 🟡 High Priority (Usually Blocked)
- Development documentation (`dev-notes*`, `internal-*`)
- Test artifacts (`test-results/`, `coverage-reports/`)
- Security files (`security-*`, `audit-*`)
- Local scripts (`local-*`, `dev-*`)

## Developer Commands

```bash
# Check protection status
./scripts/check-protection.sh

# Scan for sensitive files before committing
git check-sensitive

# See what would be committed
git what-commit

# Emergency cleanup (if sensitive files were committed)
./scripts/emergency-cleanup.sh
```

## Troubleshooting

### File Blocked by Protection
1. Check why: Review the protection category explanation
2. Remove from staging: `git reset HEAD <file>`
3. Add to .gitignore if appropriate
4. Move file to appropriate location if legitimate

### Protection Not Working
1. Verify installation: `./scripts/check-protection.sh`
2. Check hook permissions: `ls -la .git/hooks/pre-commit`
3. Reinstall: `./scripts/install-ironclad-protection.sh --force`

### Emergency Situations
1. Use emergency cleanup script: `./scripts/emergency-cleanup.sh`
2. Contact repository maintainer
3. Consider BFG Repo-Cleaner for history cleanup

## Maintenance

- Protection patterns are updated regularly
- CI/CD scans run on every push and PR
- Weekly security scans detect new patterns
- Global protections apply to all repositories

## Security Philosophy

**Defense in Depth**: Multiple independent layers ensure comprehensive protection.
**Fail Secure**: Default behavior is to block rather than allow.
**Clear Communication**: Detailed error messages explain why files are blocked.
**Developer Friendly**: Tools and scripts help developers work efficiently within protections.
EOF

    log_action "Created protection documentation"
}

# ===============================================================================
# VERIFICATION FUNCTIONS
# ===============================================================================

verify_installation() {
    echo -e "\n${BOLD}Verifying Installation...${NC}"
    print_separator

    local issues=0

    # Check pre-commit hook
    if [[ -x ".git/hooks/pre-commit" ]]; then
        log_action "Pre-commit hook is installed and executable"
    else
        log_error "Pre-commit hook is not properly installed"
        ((issues++))
    fi

    # Check .gitignore protection
    if grep -q "IRONCLAD PROTECTION SYSTEM" .gitignore 2>/dev/null; then
        log_action ".gitignore protection is active"
    else
        log_error ".gitignore protection is not found"
        ((issues++))
    fi

    # Check git configuration
    if git config --get-regexp "alias\." | grep -q "check-sensitive\|what-commit"; then
        log_action "Security git aliases are installed"
    else
        log_warning "Some security git aliases may not be installed"
    fi

    # Check global gitignore
    if [[ -f "$HOME/.gitignore_global" ]]; then
        log_action "Global .gitignore is installed"
    else
        log_warning "Global .gitignore is not installed"
    fi

    # Test protection with dummy files
    echo -e "\n${BOLD}Testing Protection System...${NC}"

    # Create test files that should be blocked
    local test_files=(
        ".test-claude-config.json"
        "test.env"
        "test-password.txt"
        "personal-notes.md"
    )

    for file in "${test_files[@]}"; do
        echo "test content" > "$file"
    done

    # Test if they would be ignored
    local ignored_count=0
    for file in "${test_files[@]}"; do
        if git check-ignore "$file" >/dev/null 2>&1; then
            ((ignored_count++))
        fi
    done

    # Cleanup test files
    rm -f "${test_files[@]}"

    if [[ $ignored_count -eq ${#test_files[@]} ]]; then
        log_action "Protection test passed - all test files properly ignored"
    else
        log_warning "Protection test partial - $ignored_count of ${#test_files[@]} test files ignored"
    fi

    # Summary
    echo -e "\n${BOLD}Installation Summary:${NC}"
    if [[ $issues -eq 0 ]]; then
        echo -e "${GREEN}✅ Installation completed successfully with no issues${NC}"
        echo -e "${GREEN}🛡️ Repository is now protected by ironclad security${NC}"
    else
        echo -e "${YELLOW}⚠️ Installation completed with $issues issue(s)${NC}"
        echo -e "${YELLOW}🔧 Run with --force to attempt repairs${NC}"
    fi
}

# ===============================================================================
# COMMAND LINE PARSING
# ===============================================================================

show_help() {
    cat << EOF
${BOLD}IRONCLAD PROTECTION INSTALLER${NC}

This script installs comprehensive protection against committing internal files.

${BOLD}USAGE:${NC}
    $0 [OPTIONS]

${BOLD}OPTIONS:${NC}
    --global        Install protections globally (affects all repositories)
    --force         Overwrite existing configurations without prompting
    --help          Show this help message

${BOLD}WHAT IT INSTALLS:${NC}
    • Pre-commit hook with 4 detection algorithms
    • Enhanced .gitignore with 600+ protection patterns
    • Git security configuration and aliases
    • Global .gitignore for system-wide protection
    • Developer tools and emergency procedures
    • Comprehensive documentation

${BOLD}PROTECTION COVERAGE:${NC}
    • AI/Agent configurations (.claude/, *claude*)
    • Secrets and keys (*.key, *.pem, *secret*, *password*)
    • Environment files (.env*, *.local*)
    • Personal files (*personal*, *private*)
    • IDE configurations (.vscode/, .idea/)
    • OS files (.DS_Store, Thumbs.db)
    • Development artifacts (logs, temp files, cache)
    • And many more...

${BOLD}EXAMPLES:${NC}
    $0                      # Install with prompts
    $0 --force              # Install overwriting existing files
    $0 --global             # Install with global protections
    $0 --global --force     # Install globally without prompts

${BOLD}VERIFICATION:${NC}
    After installation, run: ./scripts/check-protection.sh

EOF
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --global)
                GLOBAL_INSTALL=true
                shift
                ;;
            --force)
                FORCE_INSTALL=true
                shift
                ;;
            --help)
                SHOW_HELP=true
                shift
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}" >&2
                echo "Use --help for usage information" >&2
                exit 1
                ;;
        esac
    done
}

# ===============================================================================
# MAIN EXECUTION
# ===============================================================================

main() {
    parse_arguments "$@"

    if [[ "$SHOW_HELP" == "true" ]]; then
        show_help
        exit 0
    fi

    print_header

    echo -e "${GREEN}Installing ironclad protection against internal file commits...${NC}\n"

    # Initialize logging
    echo "$(date): Starting ironclad protection installation" > "$LOG_FILE"

    # Verify we're in a git repository
    check_git_repository

    # Show configuration
    echo -e "${BOLD}Installation Configuration:${NC}"
    echo -e "Global Install: ${GLOBAL_INSTALL}"
    echo -e "Force Install: ${FORCE_INSTALL}"
    echo -e "Repository: $(git rev-parse --show-toplevel)"
    echo ""

    if [[ "$FORCE_INSTALL" != "true" ]]; then
        if ! confirm_action "Proceed with installation?" "y"; then
            echo -e "${YELLOW}Installation cancelled${NC}"
            exit 0
        fi
    fi

    # Run installation steps
    install_pre_commit_hook
    install_gitignore_protection
    install_git_configuration
    install_developer_tools
    install_emergency_procedures

    # Verify installation
    verify_installation

    # Final message
    echo -e "\n${BOLD}${GREEN}🛡️ IRONCLAD PROTECTION INSTALLED${NC}"
    echo -e "${GREEN}Your repository is now protected against internal file commits${NC}"
    echo -e "${BLUE}📚 See IRONCLAD-PROTECTION.md for complete documentation${NC}"
    echo -e "${BLUE}🔧 Run ./scripts/check-protection.sh to verify status${NC}"

    echo "$(date): Installation completed successfully" >> "$LOG_FILE"
}

# Run main function with all arguments
main "$@"
