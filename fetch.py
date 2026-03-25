from app import app
app.testing = True
with app.test_client() as c:
    with c.session_transaction() as sess:
        sess['logged_in'] = True
    res = c.get('/admin?status=all')
    with open('output_proper.html', 'w', encoding='utf-8') as f:
        f.write(res.data.decode('utf-8'))
