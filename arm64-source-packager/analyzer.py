#!/usr/bin/env python3
import os

class Analyzer:
    def analyze_source(self, project_path):
        """Verifies that the source folder and requirements listing exist cleanly."""
        print(f"[*] Analyzing target project path: {project_path}")
        
        if not os.path.isdir(project_path):
            print(f"[-] Error: Target directory '{project_path}' does not exist.")
            return False
            
        req_file = os.path.join(project_path, "requirements.txt")
        if not os.path.exists(req_file):
            print(f"[-] Error: Missing critical file 'requirements.txt' inside {project_path}")
            return False
            
        print("[+] Input project folder verified successfully.")
        return True
