import React, { useState, useEffect } from 'react';
import { getWeatherForecast, updateUserLocation, searchLocation } from '../api/dashboard';

export default function WeatherWidget({ user, onLocationUpdate }) {
  const [weather, setWeather] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showLocationInput, setShowLocationInput] = useState(false);
  const [locationInput, setLocationInput] = useState('');
  const [locationSuggestions, setLocationSuggestions] = useState([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    // If user has a saved location, fetch weather automatically
    if (user?.city) {
      fetchWeather();
    } else {
      // Show location input if no saved location
      setShowLocationInput(true);
    }
  }, [user]);



  const fetchWeather = async (location = null) => {
    try {
      setLoading(true);
      setError('');
      const response = await getWeatherForecast(location);
      if (response.status === 'success') {
        setWeather(response.data);
      } else {
        setError(response.message || 'Failed to fetch weather data');
      }
    } catch (err) {
      setError('Failed to fetch weather data: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLocationSearch = async (query) => {
    if (!query.trim()) {
      setLocationSuggestions([]);
      return;
    }

    try {
      setSearching(true);
      const response = await searchLocation(query);
      if (response.status === 'success') {
        setLocationSuggestions([response.data]);
        setError(''); // Clear any previous errors
      } else {
        setLocationSuggestions([]);
        setError('Location not found. Please try a different city name.');
      }
    } catch (err) {
      setLocationSuggestions([]);
      setError('Failed to search location: ' + err.message);
    } finally {
      setSearching(false);
    }
  };

  const handleLocationSelect = async (locationData) => {
    try {
      setLoading(true);
      setError('');
      
      // Get weather for the selected location
      const weatherData = await getWeatherForecast(`${locationData.city}, ${locationData.country}`);
      if (weatherData.status === 'success') {
        setWeather(weatherData.data);
        
        // Update user's location in the database
        const response = await updateUserLocation({
          city: locationData.city,
          country: locationData.country,
          latitude: locationData.latitude,
          longitude: locationData.longitude
        });

        if (response.status === 'success') {
          // Update parent component with new location
          onLocationUpdate(response.data);
        }
        
        // Hide location input
        setShowLocationInput(false);
        setLocationInput('');
        setLocationSuggestions([]);
      } else {
        setError('Failed to get weather data for the selected location');
      }
    } catch (err) {
      setError('Failed to update location: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const getWeatherIcon = (iconCode) => {
    const iconMap = {
      '01d': 'fas fa-sun',
      '01n': 'fas fa-moon',
      '02d': 'fas fa-cloud-sun',
      '02n': 'fas fa-cloud-moon',
      '03d': 'fas fa-cloud',
      '03n': 'fas fa-cloud',
      '04d': 'fas fa-cloud',
      '04n': 'fas fa-cloud',
      '09d': 'fas fa-cloud-rain',
      '09n': 'fas fa-cloud-rain',
      '10d': 'fas fa-cloud-sun-rain',
      '10n': 'fas fa-cloud-moon-rain',
      '11d': 'fas fa-bolt',
      '11n': 'fas fa-bolt',
      '13d': 'fas fa-snowflake',
      '13n': 'fas fa-snowflake',
      '50d': 'fas fa-smog',
      '50n': 'fas fa-smog'
    };
    return iconMap[iconCode] || 'fas fa-cloud';
  };

  const getWeatherColor = (temp) => {
    if (temp < 0) return 'text-info'; // Blue for cold
    if (temp < 15) return 'text-primary'; // Light blue for cool
    if (temp < 25) return 'text-success'; // Green for mild
    if (temp < 30) return 'text-warning'; // Yellow for warm
    return 'text-danger'; // Red for hot
  };

  if (showLocationInput) {
    return (
      <div className="weather-widget text-center p-3">
        <h6 className="mb-3">
          <i className="fas fa-map-marker-alt me-2"></i>
          Select Your Location
        </h6>
        <p className="small mb-3">Enter your location to see the weather forecast</p>
        
        
        <div className="position-relative">
          <input
            type="text"
            className="form-control form-control-sm mb-2"
            placeholder="Enter your city (e.g., London, UK)"
            value={locationInput}
            onChange={(e) => {
              setLocationInput(e.target.value);
              handleLocationSearch(e.target.value);
            }}
            onKeyPress={(e) => {
              if (e.key === 'Enter' && locationSuggestions.length > 0) {
                handleLocationSelect(locationSuggestions[0]);
              }
            }}
            disabled={loading}
          />
          {searching && (
            <div className="position-absolute top-0 end-0 me-2" style={{ top: '8px' }}>
              <i className="fas fa-spinner fa-spin"></i>
            </div>
          )}
          
          {locationSuggestions.length > 0 && (
            <div className="list-group position-absolute w-100" style={{ zIndex: 1000, top: '100%' }}>
              {locationSuggestions.map((suggestion, index) => (
                <button
                  key={index}
                  className="list-group-item list-group-item-action list-group-item-sm"
                  onClick={() => handleLocationSelect(suggestion)}
                >
                  <i className="fas fa-map-marker-alt me-2"></i>
                  {suggestion.city}, {suggestion.country}
                </button>
              ))}
            </div>
          )}
          
          <button 
            className="btn btn-sm btn-light w-100"
            onClick={async () => {
              if (locationInput.trim()) {
                // If we have suggestions, select the first one
                if (locationSuggestions.length > 0) {
                  await handleLocationSelect(locationSuggestions[0]);
                } else {
                  // Otherwise, try to search again
                  await handleLocationSearch(locationInput);
                }
              }
            }}
            disabled={loading || !locationInput.trim()}
          >
            {loading ? (
              <>
                <i className="fas fa-spinner fa-spin me-1"></i>
                Searching...
              </>
            ) : (
              <>
                <i className="fas fa-search me-1"></i>
                {locationSuggestions.length > 0 ? 'Select Location' : 'Search Location'}
              </>
            )}
          </button>
        </div>
        {error && (
          <div className="alert alert-danger alert-sm mt-2 mb-0">
            {error}
          </div>
        )}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="weather-widget text-center p-3">
        <i className="fas fa-spinner fa-spin fa-2x mb-2"></i>
        <div className="fw-bold">Loading Weather...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="weather-widget text-center p-3">
        <i className="fas fa-exclamation-triangle fa-2x mb-2 text-warning"></i>
        <div className="fw-bold">Weather Unavailable</div>
        <small className="text-muted">{error}</small>
        <button 
          className="btn btn-sm btn-outline-primary mt-2"
          onClick={() => setShowLocationInput(true)}
        >
          <i className="fas fa-map-marker-alt me-1"></i>
          Change Location
        </button>
      </div>
    );
  }

  if (!weather) {
    return (
      <div className="weather-widget text-center p-3">
        <i className="fas fa-cloud fa-2x mb-2 text-muted"></i>
        <div className="fw-bold">Weather Widget</div>
        <button 
          className="btn btn-sm btn-primary mt-2"
          onClick={() => setShowLocationInput(true)}
        >
          <i className="fas fa-map-marker-alt me-1"></i>
          Set Location
        </button>
      </div>
    );
  }

  const { current, forecast } = weather;

  return (
    <div className="weather-widget">
      {/* Current Weather */}
      <div className="text-center mb-3">
        <div className="d-flex align-items-center justify-content-center mb-2">
          <i className={`${getWeatherIcon(current.icon)} fa-2x me-2`}></i>
          <div>
            <div className={`fw-bold fs-4 ${getWeatherColor(current.temperature)}`}>
              {Math.round(current.temperature)}°C
            </div>
            <div className="small text-muted">{current.description}</div>
          </div>
        </div>
        <div className="small text-muted">
          <i className="fas fa-map-marker-alt me-1"></i>
          {current.city}, {current.country}
        </div>
        <div className="small text-muted">
          Feels like {Math.round(current.feels_like)}°C
        </div>
      </div>

      {/* Weather Details */}
      <div className="row g-2 mb-3">
        <div className="col-6">
          <div className="text-center">
            <i className="fas fa-tint text-info"></i>
            <div className="small">{current.humidity}%</div>
            <div className="small text-muted">Humidity</div>
          </div>
        </div>
        <div className="col-6">
          <div className="text-center">
            <i className="fas fa-wind text-primary"></i>
            <div className="small">{Math.round(current.wind_speed * 10) / 10} m/s</div>
            <div className="small text-muted">Wind</div>
          </div>
        </div>
      </div>

      {/* 24h Forecast */}
      <div className="forecast-preview">
        <div className="small fw-bold mb-2">Next 24 Hours</div>
        <div className="d-flex overflow-auto">
          {forecast.slice(0, 4).map((item, index) => (
            <div key={index} className="text-center me-3 flex-shrink-0">
              <div className="small text-muted">
                {new Date(item.datetime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
              <i className={`${getWeatherIcon(item.icon)} mb-1`}></i>
              <div className="small fw-bold">{Math.round(item.temperature)}°</div>
            </div>
          ))}
        </div>
      </div>

      {/* Change Location Button */}
      <div className="text-center mt-3">
        <button 
          className="btn btn-sm btn-outline-secondary"
          onClick={() => setShowLocationInput(true)}
        >
          <i className="fas fa-map-marker-alt me-1"></i>
          Change Location
        </button>
      </div>
    </div>
  );
}