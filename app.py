from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# This is a simple 'Database' for now
data = {
    "total_utility": 0,
    "per_person": 0,
    "residents": [
        {"name": "Aleesha", "arrears": 500, "status": "red"}, # [cite: 6]
        {"name": "Jia", "arrears": 0, "status": "green"},    # [cite: 6]
        {"name": "Joel", "arrears": 200, "status": "yellow"} # [cite: 6]
    ]
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculate', methods=['POST'])
def calculate():
    # Automated Distribution Algorithm [cite: 17]
    total = float(request.form.get('bill_amount'))
    data["total_utility"] = total
    data["per_person"] = total / len(data["residents"])
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html', data=data)

if __name__ == '__main__':
    app.run(debug=True)