// =========================================
// INITIALIZE GEOSPATIAL MAP VIEW
// =========================================
const map = L.map('map', {
    zoomControl: false 
}).setView([-3.7575, 102.2755], 16);

L.control.zoom({ position: 'topright' }).addTo(map);

// Menggunakan OpenStreetMap Standard Layer sesuai pilihan terakhir Anda
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

// =========================================
// GEOMETRIC COORDINATES POOL
// =========================================
const locations = {
    "Gerbang Utama": [-3.760568, 102.272638],
    "Gedung Layanan Terpadu": [-3.758209, 102.272176],
    "Gerbang Kedua (Akses Gang Juwita)": [-3.759452, 102.275033],
    "Laboratorium Fisika": [-3.755810, 102.273885],
    "Gedung Bersama V": [-3.755753, 102.276481],
    "Gedung Bersama III": [-3.756111, 102.276192],
    "Gedung Serba Guna": [-3.757851, 102.276916], // SUDAH DIPERBAIKI: Menggunakan kurung siku []
    "Dekanat Teknik": [-3.758555, 102.27667],
    "Laboratorium Teknik": [-3.758911, 102.276650],
    "Gerbang Keluar": [-3.759387, 102.276240]
};

const startSelect = document.getElementById('start');
const destinationSelect = document.getElementById('destination');

Object.keys(locations).forEach(location => {
    startSelect.add(new Option(location, location));
    destinationSelect.add(new Option(location, location));
});

// Default values
startSelect.value = "Gedung Bersama V";
destinationSelect.value = "Gedung Layanan Terpadu";

let routeLine = null;
let startMarker = null;
let destinationMarker = null;

// Helper untuk membuat custom icon bergaya modern
function createCustomMarker(iconClass, glowColor) {
    return L.divIcon({
        className: 'custom-div-icon',
        html: `<div class="marker-pin-glowing" style="box-shadow: 0 0 15px ${glowColor}; background: ${glowColor};">
                 <i class="${iconClass}"></i>
               </div>`,
        iconSize: [36, 36],
        iconAnchor: [18, 18],
        popupAnchor: [0, -18]
    });
}

// =========================================
// CORE ENGINE CALLER (FIND ROUTE)
// =========================================
async function findRoute(){
    const start = startSelect.value;
    const destination = destinationSelect.value;
    const vehicle = document.getElementById('vehicle').value;

    if (routeLine) map.removeLayer(routeLine);
    if (startMarker) map.removeLayer(startMarker);
    if (destinationMarker) map.removeLayer(destinationMarker);

    const instructionsDiv = document.getElementById('instructions');
    instructionsDiv.innerHTML = `
        <div class="loading-state">
            <i class="fa-solid fa-circle-notch fa-spin"></i>
            <span>Menghitung lintasan optimal A*...</span>
        </div>`;

    try {
        const response = await fetch('http://127.0.0.1:5000/route', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start, destination, vehicle })
        });

        const data = await response.json();
        
        // JIKA FLASK MENGIRIMKAN ERROR RESPONS (Status 400/500)
        if (!response.ok) {
            throw new Error(data.message || "Gagal memproses model spasial.");
        }

        // VALIDASI AMAN: Mencegah error "reading lat" jika properti path kosong
        if (!data.path || !Array.isArray(data.path) || data.path.length === 0) {
            throw new Error("Jalur rute tidak ditemukan atau koordinat kosong.");
        }

        // Custom marker icons berdasarkan tipe lokasi
        const startIconClass = start.includes("Gerbang") ? "fa-solid fa-archway" : "fa-solid fa-building-user";
        const destIconClass = destination.includes("Gerbang") ? "fa-solid fa-archway" : "fa-solid fa-graduation-cap";

        startMarker = L.marker(locations[start], { icon: createCustomMarker(startIconClass, '#10b981') }).addTo(map)
            .bindPopup(`<div class="custom-popup"><b>Mulai Dari:</b><br>${start}</div>`);
        
        destinationMarker = L.marker(locations[destination], { icon: createCustomMarker(destIconClass, '#ef4444') }).addTo(map)
            .bindPopup(`<div class="custom-popup"><b>Tujuan Akhir:</b><br>${destination}</div>`);

        const roadCoordinates = data.path.map(point => [point.lat, point.lng]);
        const finalPathCoordinates = [locations[start], ...roadCoordinates, locations[destination]];

        // Visual warna rute
        const pathColor = vehicle === 'walk' ? '#00f2fe' : '#38ef7d';
        
        routeLine = L.polyline(finalPathCoordinates, {
            color: pathColor,
            weight: 5,
            opacity: 0.9,
            lineJoin: 'round',
            className: 'glowing-path'
        }).addTo(map);

        map.fitBounds(routeLine.getBounds(), { padding: [50, 50] });

        // Update HUD metrics
        document.getElementById('distance').innerText = `${data.distance} m`;
        document.getElementById('duration').innerText = `${data.duration} mnt`;

        // Render instruksi navigasi (Tanpa Emoticon Tambahan di Daftar Langkah)
        instructionsDiv.innerHTML = '';
        data.instructions.forEach((instruction, idx) => {
            const item = document.createElement('div');
            item.className = 'step-item';
            
            if (instruction.includes("⚠️") || instruction.includes("dilarang") || instruction.includes("ditolak")) {
                item.classList.add('step-warning');
            } else if (instruction.includes("🏁")) {
                item.classList.add('step-success');
            }
            
            item.innerHTML = `<span class="step-number">${idx + 1}</span> <div class="step-text">${instruction}</div>`;
            instructionsDiv.appendChild(item);
        });

    } catch (error) {
        // Jika error terjadi, bersihkan tampilan metrik dan tampilkan kotak error yang rapi
        document.getElementById('distance').innerText = '-';
        document.getElementById('duration').innerText = '-';
        instructionsDiv.innerHTML = `
            <div class="step-item step-error">
                <i class="fa-solid fa-triangle-exclamation" style="color: #f43f5e; margin-top: 3px;"></i>
                <div class="step-text"><b>Sistem Regulasi Beraksi:</b><br>${error.message}</div>
            </div>
        `;
    }
}

// Jalankan otomatis saat web dimuat
document.addEventListener("DOMContentLoaded", findRoute);