from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
import os
import json
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Path to store user data and uploads
USER_FILE = 'users.txt'
NOTES_FILE = 'notes.json'  # Stores metadata about uploaded notes (title, description, filename, uploader)
NOTICES_FILE = 'notices.json'  # Stores notices data
UPLOAD_FOLDER = 'uploads'

# Ensure required directories and files exist
if not os.path.exists(USER_FILE):
    open(USER_FILE, 'w').close()
    
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    
if not os.path.exists(NOTES_FILE):
    with open(NOTES_FILE, 'w') as f:
        json.dump([], f)

if not os.path.exists(NOTICES_FILE):
    with open(NOTICES_FILE, 'w') as f:
        json.dump([], f)

@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'], user_type=session['user_type'])

@app.route('/signup', methods=['GET', 'POST'])
def student_signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Check if passwords match
        if password != confirm_password:
            return render_template('signup.html', error="Passwords don't match")
            
        # Check if email already exists
        with open(USER_FILE, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3 and parts[2] == email:  # Email is at index 2
                    return render_template('signup.html', error="Email already registered")
            
        grade = request.form['grade']
        section = request.form['section']
        
        with open(USER_FILE, 'a') as f:
            f.write(f"student,{username},{email},{password},{grade},{section}\n")
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/check-email', methods=['POST'])
def check_email():
    email = request.form['email']
    
    with open(USER_FILE, 'r') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 3 and parts[2] == email:  # Email is at index 2
                return jsonify({'exists': True})
    
    return jsonify({'exists': False})

@app.route('/api/user-type', methods=['GET'])
def get_user_type():
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    return jsonify({'user_type': session.get('user_type', 'student')})

@app.route('/adminsignup', methods=['GET', 'POST'])
def teacher_signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        admin_code = request.form['admin_code']
        
        if password != confirm_password:
            return render_template('adminsignup.html', error="Passwords don't match")
        if admin_code != '1234':
            return render_template('adminsignup.html', error="Invalid admin code")
            
        # Check if email already exists
        with open(USER_FILE, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 3 and parts[2] == email:  # Email is at index 2
                    return render_template('adminsignup.html', error="Email already registered")
            
        with open(USER_FILE, 'a') as f:
            f.write(f"teacher,{username},{email},{password}\n")
        session['username'] = username
        session['user_type'] = 'teacher'
        return redirect(url_for('home'))
    return render_template('adminsignup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        with open(USER_FILE, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                # Ensure the line has enough parts to avoid IndexError
                if len(parts) < 4:
                    continue  # Skip malformed lines
                user_type = parts[0]
                stored_username = parts[1]
                stored_email = parts[2]
                stored_password = parts[3]
                if email == stored_email and password == stored_password:
                    session['username'] = stored_username
                    session['user_type'] = user_type
                    return redirect(url_for('home'))
        
        # Check if this is an AJAX request
        if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
            return "Invalid email or password", 401
        
        return render_template('login.html', error="Invalid email or password")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_type', None)
    return redirect(url_for('login'))

@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Get user details from users.txt
    user_data = {
        'username': session['username'],
        'user_type': session['user_type'],
        'email': None,
        'grade': None,
        'section': None,
        'notes_uploaded': 0,
        'notes_available': 0
    }
    
    with open(USER_FILE, 'r') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 4 and parts[1] == session['username']:
                user_data['email'] = parts[2]
                if session['user_type'] == 'student' and len(parts) >= 6:
                    user_data['grade'] = parts[4]
                    user_data['section'] = parts[5]
                break
    
    # Get statistics based on user type
    if session['user_type'] == 'teacher':
        # Count notes uploaded by this teacher
        try:
            with open(NOTES_FILE, 'r') as f:
                notes = json.load(f)
                user_data['notes_uploaded'] = len([note for note in notes if note.get('uploaded_by') == session['username']])
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    else:
        # Count notes available for this student's section
        try:
            with open(NOTES_FILE, 'r') as f:
                notes = json.load(f)
                if user_data['section']:
                    user_data['notes_available'] = len([note for note in notes if note.get('section') == user_data['section']])
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    
    return render_template('profile.html', **user_data)

@app.route('/notices')
def notices():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Load notices from JSON file
    try:
        with open(NOTICES_FILE, 'r') as f:
            notices_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        notices_data = []
    
    # Prepare data for template
    all_notices = notices_data  # Teachers see all notices
    my_class_notices = []
    student_class = None
    student_section = None
    
    if session['user_type'] == 'student':
        # Get student's class and section from users.txt
        with open(USER_FILE, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 6 and parts[0] == 'student' and parts[1] == session['username']:
                    student_class = parts[4]   # Class is at index 4
                    student_section = parts[5] # Section is at index 5
                    break
        
        if student_class and student_section:
            # Filter notices for "My Class" tab
            for notice in notices_data:
                notice_class = notice.get('class', '')
                notice_section = notice.get('section', '')
                
                # Show notices that are specifically for this student's class/section
                if (notice_class == student_class and notice_section == student_section) or \
                   (notice_class == student_class and notice_section == '') or \
                   (notice_class == '' and notice_section == student_section):
                    my_class_notices.append(notice)
            
            # For students, "All Notices" includes public notices + class-specific notices
            filtered_notices = []
            for notice in notices_data:
                notice_class = notice.get('class', '')
                notice_section = notice.get('section', '')
                
                # Public notice (both empty)
                if notice_class == '' and notice_section == '':
                    filtered_notices.append(notice)
                # Class-wide notice (class matches, section empty)
                elif notice_class == student_class and notice_section == '':
                    filtered_notices.append(notice)
                # Section-wide notice (section matches, class empty)
                elif notice_class == '' and notice_section == student_section:
                    filtered_notices.append(notice)
                # Specific class-section notice (both match)
                elif notice_class == student_class and notice_section == student_section:
                    filtered_notices.append(notice)
            
            all_notices = filtered_notices
    
    return render_template('notices.html', 
                         username=session['username'], 
                         user_type=session['user_type'], 
                         notices=all_notices,
                         my_class_notices=my_class_notices,
                         student_class=student_class,
                         student_section=student_section)

@app.route('/add-notice')
def add_notice_page():
    if 'username' not in session or session['user_type'] != 'teacher':
        return redirect(url_for('notices'))
    return render_template('add_notice.html', username=session['username'], user_type=session['user_type'])

# Notes management routes
@app.route('/notes')
def notes_page():
    if 'username' not in session or session['user_type'] != 'teacher':
        return redirect(url_for('home'))
    return render_template('notes.html')

@app.route('/api/notes', methods=['GET'])
def get_notes():
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    try:
        with open(NOTES_FILE, 'r') as f:
            notes_data = json.load(f)
        
        # If user is a student, filter notes by their section
        if session['user_type'] == 'student':
            # Get student's section from users.txt
            student_section = None
            with open(USER_FILE, 'r') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if parts[0] == 'student' and parts[1] == session['username']:
                        student_section = parts[5]  # Section is at index 5
                        break
            
            if student_section:
                notes_data = [note for note in notes_data if note.get('section') == student_section]
        
        return jsonify(notes_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/notes', methods=['POST'])
def add_note():
    if 'username' not in session or session['user_type'] != 'teacher':
        return jsonify({"error": "Not authorized"}), 403
    
    try:
        print("Form data:", request.form)
        print("Files:", request.files)
        
        if 'pdf_file' not in request.files:
            print("No file in request")
            return jsonify({"error": "No file uploaded"}), 400
            
        file = request.files['pdf_file']
        if file.filename == '':
            print("No file selected")
            return jsonify({"error": "No file selected"}), 400
            
        allowed_extensions = ('.pdf', '.doc', '.docx', '.ppt', '.pptx')
        if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
            print("Invalid file type")
            return jsonify({"error": "Only PDF, Word documents, and PowerPoint files are allowed"}), 400
        
        # Generate unique filename by adding timestamp if file exists
        base_name, extension = os.path.splitext(secure_filename(file.filename))
        filename = f"{base_name}_{int(datetime.now().timestamp())}{extension}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        # Save file with proper closure
        file.save(file_path)
        file.close()
        
        note_data = {
            "id": str(datetime.now().timestamp()),
            "title": request.form.get('title', ''),
            "description": request.form.get('description', ''),
            "subject": request.form.get('subject', ''),
            "filename": filename,
            "section": request.form.get('section', ''),
            "uploaded_at": datetime.now().isoformat(),
            "uploaded_by": session['username']
        }
        
        print("Note data to be saved:", note_data)
        
        try:
            with open(NOTES_FILE, 'r') as f:
                notes = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print("Creating new notes list")
            notes = []
        
        notes.append(note_data)
        
        with open(NOTES_FILE, 'w') as f:
            json.dump(notes, f, indent=2)
            print("Notes saved successfully")
        
        return redirect(url_for('home'))
    except Exception as e:
        print("Error:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/api/notes/<note_id>', methods=['DELETE'])
def delete_note(note_id):
    if 'username' not in session or session['user_type'] != 'teacher':
        return jsonify({"error": "Not authorized"}), 403
    
    try:
        with open(NOTES_FILE, 'r') as f:
            notes = json.load(f)
        
        # Find the note to delete
        note_to_delete = None
        updated_notes = []
        for note in notes:
            if note['id'] == note_id:
                note_to_delete = note
            else:
                updated_notes.append(note)
        
        if not note_to_delete:
            return jsonify({"error": "Note not found"}), 404
        
        # Delete the file from uploads folder with proper error handling
        file_path = os.path.join(UPLOAD_FOLDER, note_to_delete['filename'])
        try:
            if os.path.exists(file_path):
                # Ensure file is not in use
                with open(file_path, 'rb') as f:
                    f.close()
                os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file {file_path}: {str(e)}")
            # Continue with note deletion even if file deletion fails
            pass
        
        # Update the notes.json file
        with open(NOTES_FILE, 'w') as f:
            json.dump(updated_notes, f, indent=2)
        
        return jsonify({"message": "Note deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/notes/<note_id>', methods=['PUT'])
def edit_note(note_id):
    if 'username' not in session or session['user_type'] != 'teacher':
        return jsonify({"error": "Not authorized"}), 403
    
    try:
        with open(NOTES_FILE, 'r') as f:
            notes = json.load(f)
        
        # Find the note to edit
        note_index = None
        for i, note in enumerate(notes):
            if note['id'] == note_id:
                note_index = i
                break
        
        if note_index is None:
            return jsonify({"error": "Note not found"}), 404
        
        # Update note metadata
        notes[note_index]['title'] = request.form.get('title', notes[note_index]['title'])
        notes[note_index]['description'] = request.form.get('description', notes[note_index]['description'])
        notes[note_index]['subject'] = request.form.get('subject', notes[note_index]['subject'])
        notes[note_index]['section'] = request.form.get('section', notes[note_index]['section'])
        
        # Handle file update if new file is uploaded
        if 'pdf_file' in request.files:
            file = request.files['pdf_file']
            if file.filename != '':
                # Delete old file
                old_file_path = os.path.join(UPLOAD_FOLDER, notes[note_index]['filename'])
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
                
                # Save new file
                allowed_extensions = ('.pdf', '.doc', '.docx', '.ppt', '.pptx')
                if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
                    return jsonify({"error": "Only PDF, Word documents, and PowerPoint files are allowed"}), 400
                
                # Generate unique filename for the updated file
                base_name, extension = os.path.splitext(secure_filename(file.filename))
                filename = f"{base_name}_{int(datetime.now().timestamp())}{extension}"
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                
                # Save new file with proper closure
                file.save(file_path)
                file.close()
                notes[note_index]['filename'] = filename
        else:
            return jsonify({"error": "No file uploaded"}), 400
        
        # Update the notes.json file
        with open(NOTES_FILE, 'w') as f:
            json.dump(notes, f, indent=2)
        
        return jsonify({"message": "Note updated successfully", "note": notes[note_index]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/notices', methods=['POST'])
def add_notice():
    if 'username' not in session or session['user_type'] != 'teacher':
        return redirect(url_for('notices'))
    
    try:
        notice_data = {
            "id": str(datetime.now().timestamp()),
            "title": request.form.get('title', ''),
            "description": request.form.get('description', ''),
            "priority": request.form.get('priority', 'medium'),
            "class": request.form.get('class', ''),  # Empty string means all classes
            "section": request.form.get('section', ''),  # Empty string means all sections
            "created_at": datetime.now().isoformat(),
            "created_by": session['username']
        }
        
        try:
            with open(NOTICES_FILE, 'r') as f:
                notices = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            notices = []
        
        notices.append(notice_data)
        
        with open(NOTICES_FILE, 'w') as f:
            json.dump(notices, f, indent=2)
        
        return redirect(url_for('notices'))
    except Exception as e:
        return redirect(url_for('add_notice_page'))

@app.route('/api/notices/<notice_id>', methods=['DELETE'])
def delete_notice(notice_id):
    if 'username' not in session or session['user_type'] != 'teacher':
        return jsonify({"error": "Not authorized"}), 403
    
    try:
        with open(NOTICES_FILE, 'r') as f:
            notices = json.load(f)
        
        # Remove the notice with the given ID
        updated_notices = [notice for notice in notices if notice['id'] != notice_id]
        
        with open(NOTICES_FILE, 'w') as f:
            json.dump(updated_notices, f, indent=2)
        
        return jsonify({"message": "Notice deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/notices/<notice_id>', methods=['PUT'])
def edit_notice(notice_id):
    if 'username' not in session or session['user_type'] != 'teacher':
        return jsonify({"error": "Not authorized"}), 403
    
    try:
        with open(NOTICES_FILE, 'r') as f:
            notices = json.load(f)
        
        # Find the notice to edit
        notice_index = None
        for i, notice in enumerate(notices):
            if notice['id'] == notice_id:
                notice_index = i
                break
        
        if notice_index is None:
            return jsonify({"error": "Notice not found"}), 404
        
        # Update notice data
        notices[notice_index]['title'] = request.form.get('title', notices[notice_index]['title'])
        notices[notice_index]['description'] = request.form.get('description', notices[notice_index]['description'])
        notices[notice_index]['priority'] = request.form.get('priority', notices[notice_index]['priority'])
        notices[notice_index]['class'] = request.form.get('class', notices[notice_index].get('class', ''))
        notices[notice_index]['section'] = request.form.get('section', notices[notice_index].get('section', ''))
        
        # Update the notices.json file
        with open(NOTICES_FILE, 'w') as f:
            json.dump(notices, f, indent=2)
        
        return jsonify({"message": "Notice updated successfully", "notice": notices[notice_index]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/uploads/<filename>')
def download_file(filename):
    if 'username' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    app.run(debug=True)