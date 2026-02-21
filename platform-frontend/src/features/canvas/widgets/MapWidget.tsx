import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, Polyline } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default Leaflet marker icons in React/Webpack
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
    iconUrl,
    iconRetinaUrl,
    shadowUrl,
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    tooltipAnchor: [16, -28],
    shadowSize: [41, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

interface MapMarker {
    position: [number, number];
    title?: string;
    popup?: string;
}

interface MapPolyline {
    positions: [number, number][];
    color?: string;
    weight?: number;
    opacity?: number;
    popup?: string;
}

interface MapWidgetProps {
    center?: [number, number];
    zoom?: number;
    markers?: MapMarker[];
    polylines?: MapPolyline[];
    title?: string;
}

// Component to handle dynamic center updates
const ChangeView = ({ center, zoom }: { center: [number, number]; zoom: number }) => {
    const map = useMap();
    useEffect(() => {
        map.setView(center, zoom);
    }, [center, zoom, map]);
    return null;
}

const MapWidget: React.FC<MapWidgetProps> = ({
    center = [51.505, -0.09],
    zoom = 13,
    markers = [],
    polylines = [],
    title
}) => {
    return (
        <div className="w-full h-96 rounded-lg overflow-hidden border border-gray-700 shadow-xl flex flex-col z-0">
            {title && (
                <div className="bg-gray-800 px-4 py-2 border-b border-gray-700">
                    <h3 className="text-sm font-semibold text-gray-300">{title}</h3>
                </div>
            )}
            <div className="flex-1 relative z-0">
                <MapContainer
                    center={center}
                    zoom={zoom}
                    scrollWheelZoom={false}
                    className="w-full h-full"
                >
                    <ChangeView center={center} zoom={zoom} />
                    <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />
                    {markers.map((marker, idx) => (
                        <Marker key={idx} position={marker.position} title={marker.title}>
                            {marker.popup && <Popup>{marker.popup}</Popup>}
                        </Marker>
                    ))}
                    {polylines.map((line, idx) => (
                        <Polyline
                            key={`poly-${idx}`}
                            positions={line.positions}
                            pathOptions={{
                                color: line.color || '#3b82f6',
                                weight: line.weight || 3,
                                opacity: line.opacity || 0.8
                            }}
                        >
                            {line.popup && <Popup>{line.popup}</Popup>}
                        </Polyline>
                    ))}
                </MapContainer>
            </div>
        </div>
    );
};

export default MapWidget;
