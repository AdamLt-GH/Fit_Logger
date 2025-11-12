// src/utils/refreshSystem.js

// Custom event system for global refresh notifications
class RefreshSystem {
  constructor() {
    this.listeners = new Map();
  }

  // Subscribe to refresh events
  subscribe(eventType, callback) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, []);
    }
    this.listeners.get(eventType).push(callback);
  }

  // Unsubscribe from refresh events
  unsubscribe(eventType, callback) {
    if (this.listeners.has(eventType)) {
      const callbacks = this.listeners.get(eventType);
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  // Emit refresh event
  emit(eventType, data = null) {
    if (this.listeners.has(eventType)) {
      this.listeners.get(eventType).forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error('Error in refresh callback:', error);
        }
      });
    }
  }

  // Convenience methods for specific refresh types
  refreshExercises() {
    this.emit('exercises_changed');
  }

  refreshChallenges() {
    this.emit('challenges_changed');
  }

  refreshUsers() {
    this.emit('users_changed');
  }

  refreshAll() {
    this.emit('system_refresh');
  }
}

// Create a singleton instance
const refreshSystem = new RefreshSystem();

export default refreshSystem;
