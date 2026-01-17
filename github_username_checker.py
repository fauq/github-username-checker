import requests
import time
import random
import string
import threading
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

THREADS = 3  # Number of concurrent checking threads (Keep low to avoid bans)
CHECK_DELAY = 1.5  # Base delay between requests
RESULTS_FILE = "available_usernames.txt"

# ═══════════════════════════════════════════════════════════════════════════
# CONSOLE COLORS
# ═══════════════════════════════════════════════════════════════════════════

class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Regular colors
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright colors
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

# ═══════════════════════════════════════════════════════════════════════════
# BANNER
# ═══════════════════════════════════════════════════════════════════════════

BANNER = f"""
{Color.BRIGHT_CYAN}╔════════════════════════════════════════════════════════════════════╗
║  {Color.BRIGHT_WHITE}  ██████╗ ██╗████████╗██╗   ██╗██╗   ██╗██████╗                   {Color.BRIGHT_CYAN}║
║  {Color.BRIGHT_WHITE} ██╔════╝ ██║╚══██╔══╝██║   ██║██║   ██║██╔══██╗                  {Color.BRIGHT_CYAN}║
║  {Color.BRIGHT_WHITE} ██║   ███╗██║   ██║   ███████║██║   ██║██████╔╝                  {Color.BRIGHT_CYAN}║
║  {Color.BRIGHT_WHITE} ██║   ██║██║   ██║   ██╔══██║██║   ██║██╔══██╗                   {Color.BRIGHT_CYAN}║
║  {Color.BRIGHT_WHITE} ╚██████╔╝██║   ██║   ██║  ██║╚██████╔╝██████╔╝                   {Color.BRIGHT_CYAN}║
║  {Color.BRIGHT_WHITE}  ╚═════╝ ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═════╝                    {Color.BRIGHT_CYAN}║
║                                                                    ║
║  {Color.DIM}                  made with <3 by romergan                        {Color.BRIGHT_CYAN}║
╚════════════════════════════════════════════════════════════════════╝{Color.RESET}
"""

# ═══════════════════════════════════════════════════════════════════════════
# STATISTICS TRACKER
# ═══════════════════════════════════════════════════════════════════════════

class Stats:
    def __init__(self):
        self.checked = 0
        self.available = 0
        self.taken = 0
        self.reserved = 0
        self.errors = 0
        self.lock = threading.Lock()
        self.start_time = time.time()
        
    def increment(self, category):
        with self.lock:
            if category == "checked":
                self.checked += 1
            elif category == "available":
                self.available += 1
            elif category == "taken":
                self.taken += 1
            elif category == "reserved":
                self.reserved += 1
            elif category == "errors":
                self.errors += 1
    
    def get_stats(self):
        with self.lock:
            return {
                "checked": self.checked,
                "available": self.available,
                "taken": self.taken,
                "reserved": self.reserved,
                "errors": self.errors,
                "elapsed": time.time() - self.start_time
            }

stats = Stats()

# ═══════════════════════════════════════════════════════════════════════════
# GITHUB RESERVED USERNAMES (Common ones)
# ═══════════════════════════════════════════════════════════════════════════

RESERVED_KEYWORDS = {
    'about', 'abuse', 'account', 'admin', 'api', 'apps', 'archive',
    'blog', 'business', 'collections', 'contact', 'dashboard', 'desktop',
    'dev', 'docs', 'enterprise', 'events', 'explore', 'features',
    'followers', 'following', 'gist', 'gists', 'help', 'home',
    'issues', 'jobs', 'login', 'logout', 'marketplace', 'new',
    'news', 'notifications', 'orgs', 'organizations', 'pricing',
    'private', 'public', 'pulls', 'repositories', 'search', 'security',
    'settings', 'shop', 'site', 'sponsors', 'status', 'support',
    'team', 'teams', 'topics', 'tos', 'trending', 'www', 'abuse', 'security'
}

# ═══════════════════════════════════════════════════════════════════════════
# USERNAME VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

def is_valid_github_username(username):
    if not username or len(username) < 1 or len(username) > 39:
        return False
    
    if username.lower() in RESERVED_KEYWORDS:
        return False
    
    if not all(c.isalnum() or c == '-' for c in username):
        return False
    
    if username.startswith('-') or username.endswith('-'):
        return False
    
    if '--' in username:
        return False
    
    return True

# ═══════════════════════════════════════════════════════════════════════════
# USERNAME AVAILABILITY CHECKER
# ═══════════════════════════════════════════════════════════════════════════

def check_username_via_profile(username):
    try:
        url = f"https://github.com/{username}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=False)
        
        if response.status_code == 200:
            return 'taken'
        elif response.status_code == 404:
            if username in RESERVED_KEYWORDS:
                return 'reserved'
            return 'available'
        elif response.status_code == 429:
            return 'rate_limited'
        else:
            return 'error'
    
    except requests.RequestException:
        return 'error'

# ═══════════════════════════════════════════════════════════════════════════
# USERNAME GENERATION LOGIC
# ═══════════════════════════════════════════════════════════════════════════

def generate_username(length, include_numbers=False):
    if include_numbers:
        first_char = random.choice(string.ascii_lowercase)
        rest = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length-1))
        return first_char + rest
    else:
        return ''.join(random.choices(string.ascii_lowercase, k=length))

def generate_aesthetic_string():
    vowels = "aeiou"
    consonants = "bcdfghjklmnpqrstvwxyz"
    
    patterns = ['CVCV', 'CVCV', 'VCVC', 'CVVC', 'VCCV'] # Weight CVCV slightly higher
    pattern = random.choice(patterns)
    
    result = ""
    for p in pattern:
        if p == 'C':
            result += random.choice(consonants)
        else:
            result += random.choice(vowels)
    return result

def generate_usernames_batch(count, length_min=None, length_max=None, include_numbers=False, mode="standard"):
    usernames = set()
    attempts = 0
    max_attempts = count * 100  # Safety break
    
    print(f"{Color.CYAN}[*] Generating {count:,} unique usernames...{Color.RESET}")
    sys.stdout.flush()
    
    while len(usernames) < count and attempts < max_attempts:
        if mode == "aesthetic":
            username = generate_aesthetic_string()
        else:
            length = random.randint(length_min, length_max)
            username = generate_username(length, include_numbers)
        
        if is_valid_github_username(username):
            usernames.add(username)
        
        attempts += 1
        
        if len(usernames) % 5000 == 0 and len(usernames) > 0:
            print(f"{Color.DIM}  → {len(usernames):,}/{count:,} generated...{Color.RESET}")
            sys.stdout.flush()
    
    result = list(usernames)
    
    if len(result) < count:
        print(f"{Color.YELLOW}[!] Warning: Only could generate {len(result)} unique names (space exhausted?){Color.RESET}")
    
    print(f"{Color.GREEN}[✓] Generated {len(result):,} unique usernames{Color.RESET}")
    sys.stdout.flush()
    
    return result

# ═══════════════════════════════════════════════════════════════════════════
# CHECKER WORKER
# ═══════════════════════════════════════════════════════════════════════════

def check_username_worker(username):
    delay = CHECK_DELAY + random.uniform(-0.3, 0.5)
    time.sleep(max(0.5, delay))
    
    result = check_username_via_profile(username)
    stats.increment("checked")
    
    if result == 'available':
        stats.increment("available")
        print(f"{Color.BRIGHT_GREEN}  [✓] AVAILABLE: {username:<20} 🎉{Color.RESET}")
        sys.stdout.flush()
        save_username(username)
        return ('available', username)
    
    elif result == 'taken':
        stats.increment("taken")
        print(f"{Color.DIM}  [✗] Taken:     {username:<20}{Color.RESET}")
        sys.stdout.flush()
        return ('taken', username)
    
    elif result == 'reserved':
        stats.increment("reserved")
        print(f"{Color.YELLOW}  [⊘] Reserved:  {username:<20}{Color.RESET}")
        sys.stdout.flush()
        return ('reserved', username)
    
    elif result == 'rate_limited':
        stats.increment("errors")
        print(f"{Color.BRIGHT_YELLOW}  [!] RATE LIMITED - Cooling down for 3 minutes...{Color.RESET}")
        sys.stdout.flush()
        time.sleep(180)
        return ('rate_limited', username)
    
    else:
        stats.increment("errors")
        print(f"{Color.RED}  [⚠] Error:     {username:<20}{Color.RESET}")
        sys.stdout.flush()
        return ('error', username)

# ═══════════════════════════════════════════════════════════════════════════
# SAVE RESULTS
# ═══════════════════════════════════════════════════════════════════════════

def save_username(username):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(RESULTS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{username} | Found: {timestamp}\n")
    except Exception as e:
        print(f"{Color.RED}[!] Error saving username: {e}{Color.RESET}")

# ═══════════════════════════════════════════════════════════════════════════
# MAIN CONTROL
# ═══════════════════════════════════════════════════════════════════════════

def run_checker(usernames):
    global stats
    stats = Stats()
    total = len(usernames)
    
    print(f"\n{Color.BRIGHT_CYAN}╔════════════════════════════════════════════════════════════════════╗")
    print(f"║  {Color.BRIGHT_WHITE}CHECKING {total:,} USERNAMES{' ' * (48 - len(str(total)))}║{Color.BRIGHT_CYAN}")
    print(f"╚════════════════════════════════════════════════════════════════════╝{Color.RESET}\n")
    
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = [executor.submit(check_username_worker, username) for username in usernames]
        
        completed = 0
        try:
            for future in as_completed(futures):
                completed += 1
                if completed % 20 == 0 or completed == total:
                    s = stats.get_stats()
                    progress = (completed / total) * 100
                    rate = completed / s['elapsed'] if s['elapsed'] > 0 else 0
                    eta = (total - completed) / rate if rate > 0 else 0
                    
                    print(f"\n{Color.BRIGHT_CYAN}  ╭─ Progress: {completed}/{total} ({progress:.1f}%) │ "
                          f"Rate: {rate:.1f}/s │ ETA: {int(eta)}s │ "
                          f"Found: {Color.BRIGHT_GREEN}{s['available']}{Color.BRIGHT_CYAN} ─╮{Color.RESET}\n")
                    sys.stdout.flush()
        
        except KeyboardInterrupt:
            print(f"\n{Color.YELLOW}[!] Interrupted - finishing current checks...{Color.RESET}")
            executor.shutdown(wait=False)
    
    print_final_stats()

def print_final_stats():
    s = stats.get_stats()
    rate = s['checked'] / s['elapsed'] if s['elapsed'] > 0 else 0
    time_str = f"{s['elapsed']:.1f}s @ {rate:.2f} checks/sec"
    padding = ' ' * (44 - len(time_str))
    
    print(f"\n{Color.BRIGHT_CYAN}╔════════════════════════════════════════════════════════════════════╗")
    print(f"║  {Color.BRIGHT_WHITE}FINAL RESULTS{' ' * 51}║{Color.BRIGHT_CYAN}")
    print(f"╠════════════════════════════════════════════════════════════════════╣")
    print(f"║  {Color.BRIGHT_WHITE}Total Checked:{Color.RESET}     {s['checked']:<47}{Color.BRIGHT_CYAN}║")
    print(f"║  {Color.BRIGHT_GREEN}✓ Available:{Color.RESET}       {s['available']:<47}{Color.BRIGHT_CYAN}║")
    print(f"║  {Color.DIM}✗ Taken:{Color.RESET}           {s['taken']:<47}{Color.BRIGHT_CYAN}║")
    print(f"║  {Color.BRIGHT_WHITE}Time Elapsed:{Color.RESET}      {time_str}{padding}{Color.BRIGHT_CYAN}║")
    print(f"╚════════════════════════════════════════════════════════════════════╝{Color.RESET}\n")

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def display_menu():
    print(f"{Color.BRIGHT_CYAN}╔════════════════════════════════════════════════════════════════════╗")
    print(f"║  {Color.BRIGHT_WHITE}SELECT USERNAME GENERATION MODE{Color.BRIGHT_CYAN}{' ' * 35}║{Color.BRIGHT_CYAN}")
    print(f"╠════════════════════════════════════════════════════════════════════╣")
    print(f"║                                                                    ║")
    print(f"║  {Color.BRIGHT_WHITE}[1]{Color.RESET} 3-letter usernames         {Color.DIM}(abc){Color.RESET}{' ' * 30}{Color.BRIGHT_CYAN}║")
    print(f"║  {Color.BRIGHT_WHITE}[2]{Color.RESET} 4-letter usernames         {Color.DIM}(abcd){Color.RESET}{' ' * 29}{Color.BRIGHT_CYAN}║")
    print(f"║  {Color.BRIGHT_WHITE}[3]{Color.RESET} 5-letter usernames         {Color.DIM}(abcde){Color.RESET}{' ' * 28}{Color.BRIGHT_CYAN}║")
    print(f"║  {Color.BRIGHT_WHITE}[4]{Color.RESET} 3-5 letter mix             {Color.DIM}(random length){Color.RESET}{' ' * 20}{Color.BRIGHT_CYAN}║")
    print(f"║  {Color.BRIGHT_WHITE}[5]{Color.RESET} 4-6 letter mix             {Color.DIM}(random length){Color.RESET}{' ' * 20}{Color.BRIGHT_CYAN}║")
    print(f"║  {Color.BRIGHT_WHITE}[6]{Color.RESET} 3-5 alphanumeric           {Color.DIM}(includes numbers){Color.RESET}{' ' * 17}{Color.BRIGHT_CYAN}║")
    print(f"║  {Color.BRIGHT_WHITE}[7]{Color.RESET} Custom length range        {Color.DIM}(you choose){Color.RESET}{' ' * 23}{Color.BRIGHT_CYAN}║")
    print(f"║  {Color.BRIGHT_WHITE}[8]{Color.RESET} Check single username      {Color.DIM}(manual check){Color.RESET}{' ' * 21}{Color.BRIGHT_CYAN}║")
    print(f"║                                                                    ║")
    print(f"║  {Color.BRIGHT_MAGENTA}[9] Aesthetic 4-letter         {Color.DIM}(clean/pronounceable){Color.RESET}{' ' * 14}{Color.BRIGHT_CYAN}║")
    print(f"║  {Color.BRIGHT_WHITE}[0]{Color.RESET} Exit                       {' ' * 35}{Color.BRIGHT_CYAN}║")
    print(f"║                                                                    ║")
    print(f"╚════════════════════════════════════════════════════════════════════╝{Color.RESET}")
    print()

def check_single_username():
    print(f"\n{Color.CYAN}[?] Enter username to check:{Color.RESET}")
    username = input(f"    {Color.BRIGHT_WHITE}>{Color.RESET} ").strip().lower()
    if not username: return
    
    print(f"\n{Color.CYAN}[*] Checking: {username}{Color.RESET}")
    result = check_username_via_profile(username)
    
    if result == 'available':
        print(f"\n{Color.BRIGHT_GREEN}  [✓] '{username}' IS AVAILABLE!{Color.RESET}")
        save_username(username)
    elif result == 'taken':
        print(f"\n{Color.RED}  [✗] '{username}' is taken{Color.RESET}")
    elif result == 'reserved':
        print(f"\n{Color.YELLOW}  [⊘] '{username}' is reserved{Color.RESET}")
    else:
        print(f"\n{Color.RED}[!] Error checking{Color.RESET}")

def main():
    if os.name == 'nt': os.system('')
    
    while True:
        clear_screen()
        print(BANNER)
        display_menu()
        
        choice = input(f"  {Color.BRIGHT_WHITE}Select option:{Color.RESET} ").strip()
        
        if choice == '0': break
        elif choice == '8':
            check_single_username()
            input(f"\n{Color.DIM}Press Enter...{Color.RESET}")
            continue

        # Setup generation parameters
        length_min, length_max, include_numbers = 0, 0, False
        mode = "standard"
        
        if choice == '1':
            length_min, length_max = 3, 3
        elif choice == '2':
            length_min, length_max = 4, 4
        elif choice == '3':
            length_min, length_max = 5, 5
        elif choice == '4':
            length_min, length_max = 3, 5
        elif choice == '5':
            length_min, length_max = 4, 6
        elif choice == '6':
            length_min, length_max = 3, 5
            include_numbers = True
        elif choice == '7':
            try:
                length_min = int(input(f"  Min len: "))
                length_max = int(input(f"  Max len: "))
            except: continue
        elif choice == '9':
            mode = "aesthetic"
        else:
            continue
            
        try:
            print(f"\n{Color.CYAN}[?] How many usernames?{Color.RESET}")
            count = int(input(f"    {Color.BRIGHT_WHITE}>{Color.RESET} ").strip())
            if count <= 0: continue
            
            usernames = generate_usernames_batch(count, length_min, length_max, include_numbers, mode)
            
            if usernames:
                print(f"{Color.DIM}  Preview: {', '.join(usernames[:8])}...{Color.RESET}")
                input(f"\n{Color.DIM}Press Enter to start...{Color.RESET}")
                run_checker(usernames)
                input(f"\n{Color.DIM}Press Enter...{Color.RESET}")
                
        except ValueError:
            pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)