const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

// Get authentication token from localStorage
const getAuthHeaders = () => {
  const token = localStorage.getItem('token');
  console.log('Dashboard API - Token from localStorage:', token ? token.substring(0, 20) + '...' : 'No token');
  return {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` })
  };
};

// Get dashboard data
export const getDashboardData = async () => {
  const headers = getAuthHeaders();
  console.log('Dashboard API - Making request to:', `${API_BASE}/api/dashboard/`);
  console.log('Dashboard API - Headers:', headers);
  
  const response = await fetch(`${API_BASE}/dashboard/`, {
    method: 'GET',
    headers: headers,
  });
  
  console.log('Dashboard API - Response status:', response.status);
  
  if (!response.ok) {
    const errorText = await response.text();
    console.log('Dashboard API - Error response:', errorText);
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return response.json();
};

// Get challenge detail
export const getChallengeDetail = async (challengeId) => {
  const response = await fetch(`${API_BASE}/challenge/${challengeId}/`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  const data = await response.json();
  return { status: 'success', data: data.data }; // Return in expected format
};

// Join a challenge
export const joinChallenge = async (challengeId) => {
  const response = await fetch(`${API_BASE}/challenge/${challengeId}/join/`, {
    method: 'POST',
    headers: getAuthHeaders(),
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return response.json();
};

// Leave a challenge
export const leaveChallenge = async (challengeId) => {
  const response = await fetch(`${API_BASE}/challenge/${challengeId}/leave/`, {
    method: 'POST',
    headers: getAuthHeaders(),
  });
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
  }
  
  const data = await response.json();
  return { status: 'success', ...data };
};

// Create a new challenge
export const createChallenge = async (challengeData) => {
  const response = await fetch(`${API_BASE}/challenge/create/`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(challengeData),
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return response.json();
};

// Get available exercises
export const getExercises = async () => {
  const response = await fetch(`${API_BASE}/exercises/`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return response.json();
};

// Weather API functions
export const updateUserLocation = async (locationData) => {
  const response = await fetch(`${API_BASE}/weather/location/update/`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(locationData),
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return response.json();
};

export const getWeatherForecast = async (location = null, latitude = null, longitude = null) => {
  let url = `${API_BASE}/api/weather/forecast/`;
  
  if (location) {
    url += `?location=${encodeURIComponent(location)}`;
  } else if (latitude && longitude) {
    url += `?lat=${latitude}&lon=${longitude}`;
  }
    
  const response = await fetch(url, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return response.json();
};

export const searchLocation = async (query) => {
  const response = await fetch(`${API_BASE}/api/weather/location/search/?q=${encodeURIComponent(query)}`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return response.json();
};
