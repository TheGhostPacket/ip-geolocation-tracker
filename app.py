from flask import Flask, render_template, request, jsonify
import requests
import json
import ipaddress
import re
from datetime import datetime

app = Flask(__name__)

# Free IP geolocation APIs (no API key required)
GEOLOCATION_APIS = [
    'http://ip-api.com/json/',  # Primary API
    'https://ipapi.co/',        # Backup API
]

def validate_ip_address(ip):
    """Validate if the input is a valid IP address"""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def is_private_ip(ip):
    """Check if IP is private/local"""
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private
    except ValueError:
        return False

def get_client_ip(request):
    """Get the real client IP address"""
    # Check for forwarded IP first
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        ip = request.headers.get('X-Real-IP')
    else:
        ip = request.remote_addr
    
    # If it's localhost, use a public IP for demo
    if ip in ['127.0.0.1', 'localhost', '::1']:
        ip = '8.8.8.8'  # Google's DNS for demo
    
    return ip

def lookup_ip_geolocation(ip_address):
    """Look up IP geolocation using multiple APIs"""
    
    # First, try ip-api.com (most detailed free API)
    try:
        url = f"http://ip-api.com/json/{ip_address}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query"
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('status') == 'success':
            # Determine risk level based on various factors
            risk_level = determine_risk_level(data)
            
            return {
                'success': True,
                'ip': data.get('query', ip_address),
                'country': data.get('country', 'Unknown'),
                'country_code': data.get('countryCode', 'UN'),
                'region': data.get('regionName', 'Unknown'),
                'city': data.get('city', 'Unknown'),
                'zip_code': data.get('zip', 'Unknown'),
                'latitude': data.get('lat'),
                'longitude': data.get('lon'),
                'timezone': data.get('timezone', 'Unknown'),
                'isp': data.get('isp', 'Unknown'),
                'organization': data.get('org', 'Unknown'),
                'as_info': data.get('as', 'Unknown'),
                'risk_level': risk_level,
                'is_private': is_private_ip(ip_address),
                'lookup_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
            }
        else:
            raise Exception(data.get('message', 'API request failed'))
            
    except Exception as e:
        # Try backup API (ipapi.co)
        try:
            backup_url = f"https://ipapi.co/{ip_address}/json/"
            response = requests.get(backup_url, timeout=10)
            data = response.json()
            
            if 'error' not in data:
                return {
                    'success': True,
                    'ip': ip_address,
                    'country': data.get('country_name', 'Unknown'),
                    'country_code': data.get('country_code', 'UN'),
                    'region': data.get('region', 'Unknown'),
                    'city': data.get('city', 'Unknown'),
                    'zip_code': data.get('postal', 'Unknown'),
                    'latitude': data.get('latitude'),
                    'longitude': data.get('longitude'),
                    'timezone': data.get('timezone', 'Unknown'),
                    'isp': data.get('org', 'Unknown'),
                    'organization': data.get('org', 'Unknown'),
                    'as_info': data.get('asn', 'Unknown'),
                    'risk_level': 'Unknown',
                    'is_private': is_private_ip(ip_address),
                    'lookup_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
                }
            else:
                raise Exception('Backup API also failed')
                
        except Exception as backup_error:
            return {
                'success': False,
                'error': f'Failed to lookup IP: {str(e)}',
                'ip': ip_address
            }

def determine_risk_level(data):
    """Determine risk level based on geolocation data"""
    risk_factors = []
    
    # Check for known high-risk countries (simplified example)
    high_risk_countries = ['CN', 'RU', 'KP', 'IR']  # Example list
    medium_risk_countries = ['VN', 'IN', 'PK', 'BD']  # Example list
    
    country_code = data.get('countryCode', '')
    
    if country_code in high_risk_countries:
        risk_factors.append('high_risk_country')
    elif country_code in medium_risk_countries:
        risk_factors.append('medium_risk_country')
    
    # Check for hosting/VPS providers (common for malicious activity)
    isp = data.get('isp', '').lower()
    org = data.get('org', '').lower()
    
    hosting_keywords = ['hosting', 'server', 'cloud', 'vps', 'dedicated', 'datacenter', 'digital ocean', 'aws', 'azure']
    
    if any(keyword in isp for keyword in hosting_keywords) or any(keyword in org for keyword in hosting_keywords):
        risk_factors.append('hosting_provider')
    
    # Determine overall risk level
    if len(risk_factors) >= 2:
        return 'High'
    elif len(risk_factors) == 1:
        return 'Medium'
    else:
        return 'Low'

def get_ip_reputation(ip_address):
    """Get IP reputation from threat intelligence (simplified)"""
    # This is a placeholder - in a real app, you'd use threat intel APIs
    # like AbuseIPDB, VirusTotal, etc.
    return {
        'is_malicious': False,
        'abuse_confidence': 0,
        'last_seen': None,
        'threat_types': []
    }

# Routes
@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/lookup', methods=['POST'])
def api_lookup():
    """API endpoint to lookup IP geolocation"""
    try:
        data = request.get_json()
        ip_address = data.get('ip', '').strip()
        
        if not ip_address:
            return jsonify({'success': False, 'error': 'IP address is required'}), 400
        
        # Validate IP address format
        if not validate_ip_address(ip_address):
            return jsonify({'success': False, 'error': 'Invalid IP address format'}), 400
        
        # Perform geolocation lookup
        result = lookup_ip_geolocation(ip_address)
        
        if result['success']:
            # Add reputation data (placeholder)
            result['reputation'] = get_ip_reputation(ip_address)
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/my-ip')
def api_my_ip():
    """API endpoint to get client's IP and location"""
    try:
        client_ip = get_client_ip(request)
        result = lookup_ip_geolocation(client_ip)
        
        if result['success']:
            result['is_client_ip'] = True
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/bulk-lookup', methods=['POST'])
def api_bulk_lookup():
    """API endpoint for bulk IP lookup (up to 10 IPs)"""
    try:
        data = request.get_json()
        ip_list = data.get('ips', [])
        
        if not ip_list:
            return jsonify({'success': False, 'error': 'IP list is required'}), 400
            
        if len(ip_list) > 10:
            return jsonify({'success': False, 'error': 'Maximum 10 IPs allowed'}), 400
        
        results = []
        for ip in ip_list:
            ip = ip.strip()
            if validate_ip_address(ip):
                result = lookup_ip_geolocation(ip)
                results.append(result)
            else:
                results.append({
                    'success': False,
                    'ip': ip,
                    'error': 'Invalid IP address format'
                })
        
        return jsonify({
            'success': True,
            'results': results,
            'total_processed': len(results)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)