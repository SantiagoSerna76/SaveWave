/**
 * Build script for SaveWave Native App
 * Generates the www folder and syncs with Capacitor
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const WWW_DIR = path.join(__dirname, 'www');

console.log('🔨 Building SaveWave Native App...');

// Ensure www directory exists
if (!fs.existsSync(WWW_DIR)) {
    fs.mkdirSync(WWW_DIR, { recursive: true });
}

// Copy index.html
console.log('📄 Copying index.html...');
// Already in place

// Initialize Capacitor if not done
console.log('⚡ Initializing Capacitor...');
try {
    execSync('npx cap init SaveWave com.savewave.app --webDir=www --no-git', { 
        cwd: __dirname, 
        stdio: 'inherit' 
    });
} catch (e) {
    console.log('⚠️  Capacitor already initialized or error (continuing)...');
}

// Sync Android
console.log('📱 Syncing Android project...');
try {
    execSync('npx cap sync android', { 
        cwd: __dirname, 
        stdio: 'inherit' 
    });
} catch (e) {
    console.error('❌ Error syncing Android:', e.message);
    process.exit(1);
}

console.log('✅ Build complete!');
console.log('');
console.log('📱 To open in Android Studio:');
console.log('   cd savewave-app && npx cap open android');
console.log('');
console.log('📦 To build APK:');
console.log('   cd savewave-app/android && ./gradlew assembleRelease');
console.log('');
console.log('📱 To install on device:');
console.log('   cd savewave-app/android && ./gradlew installDebug');