import sqlite3
c = sqlite3.connect('saas.db')

# Delete demo user (id=2) and all their data
c.execute('DELETE FROM posts WHERE account_id IN (SELECT id FROM accounts WHERE user_id = 2)')
c.execute('DELETE FROM schedules WHERE account_id IN (SELECT id FROM accounts WHERE user_id = 2)')
c.execute('DELETE FROM accounts WHERE user_id = 2')
c.execute('DELETE FROM users WHERE id = 2')
c.commit()

rows = c.execute('SELECT id, email, name, plan FROM users').fetchall()
for r in rows:
    print(r)
