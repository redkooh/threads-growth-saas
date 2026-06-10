import hashlib

# Test account: sha256(password + salt)
salt1 = '9f5bd6d543a0351a0a6c14a67ba546da'
hash1 = '7c5228f678b74eaba8c6c036bf84be31d2a50636209c28a79102419961a2661a'

for pw in ['test', 'test123', 'Test123', 'TestUser', 'password', 'admin', 'pass123']:
    h = hashlib.sha256((pw + salt1).encode()).hexdigest()
    match = '<<<' if h == hash1 else ''
    if match:
        print(f'{match} FOUND: {pw}')
        break

# Demo account
salt2 = 'c695a1bd5f96a025ba1f88f17e6c068b'
hash2 = 'f7bf790c3b8b67be3a5c26e454dd01b04bffcd80e76f36eadb67dfb3fd6f162f'

for pw in ['demo', 'demo123', 'Demo123', 'DemoUser', 'password', 'admin']:
    h = hashlib.sha256((pw + salt2).encode()).hexdigest()
    match = '<<<' if h == hash2 else ''
    if match:
        print(f'{match} FOUND demo: {pw}')
        break
