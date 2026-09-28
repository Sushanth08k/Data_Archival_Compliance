/**
 * Authentication service with Firebase Auth and backend JWT token synchronization.
 * Supports:
 * - Google Sign-In (Firebase popup)
 * - Email & Password (Firebase Authentication)
 * - Automatic backend sync to local database
 * - Deterministic fallback when Firebase credentials are not yet entered
 */

import api from './api';
import { auth, googleProvider, isFirebaseConfigured } from '../config/firebase';
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  updateProfile,
  signOut as firebaseSignOut,
} from 'firebase/auth';

const authService = {
  isFirebaseConfigured() {
    return isFirebaseConfigured;
  },

  async syncWithBackend(email, fullName, firebaseUid, role = 'COMPLIANCE_ANALYST') {
    const res = await api.post('/auth/firebase-sync', {
      email,
      full_name: fullName,
      firebase_uid: firebaseUid,
      role,
    });
    const { access_token, user } = res.data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('user', JSON.stringify(user));
    return res.data;
  },

  async loginWithGoogle() {
    if (!isFirebaseConfigured || !auth || !googleProvider) {
      throw new Error(
        'Firebase configuration is missing or incomplete. Please paste your Firebase Web SDK config keys into frontend/.env.'
      );
    }
    const result = await signInWithPopup(auth, googleProvider);
    const fbUser = result.user;
    return this.syncWithBackend(fbUser.email, fbUser.displayName, fbUser.uid);
  },

  async loginWithFirebaseEmail(email, password) {
    if (!isFirebaseConfigured || !auth) {
      throw new Error(
        'Firebase configuration is missing. Please paste your Firebase Web SDK config keys into frontend/.env.'
      );
    }
    const result = await signInWithEmailAndPassword(auth, email, password);
    const fbUser = result.user;
    return this.syncWithBackend(fbUser.email, fbUser.displayName, fbUser.uid);
  },

  async registerWithFirebaseEmail(email, password, fullName, role = 'COMPLIANCE_ANALYST') {
    if (!isFirebaseConfigured || !auth) {
      throw new Error(
        'Firebase configuration is missing. Please paste your Firebase Web SDK config keys into frontend/.env.'
      );
    }
    const result = await createUserWithEmailAndPassword(auth, email, password);
    const fbUser = result.user;
    if (fullName) {
      try {
        await updateProfile(fbUser, { displayName: fullName });
      } catch (err) {
        console.warn('Could not update Firebase profile name:', err);
      }
    }
    return this.syncWithBackend(fbUser.email, fullName || fbUser.displayName, fbUser.uid, role);
  },

  async login(email, password) {
    // If Firebase is configured, attempt Firebase email sign-in first
    if (isFirebaseConfigured && auth) {
      try {
        return await this.loginWithFirebaseEmail(email, password);
      } catch (firebaseErr) {
        // Fallback to local DB login if Firebase fails or user exists locally
        try {
          const response = await api.post('/auth/login', { email, password });
          const { access_token, user } = response.data;
          localStorage.setItem('access_token', access_token);
          localStorage.setItem('user', JSON.stringify(user));
          return response.data;
        } catch {
          throw firebaseErr;
        }
      }
    }

    // Direct backend login fallback
    const response = await api.post('/auth/login', { email, password });
    const { access_token, user } = response.data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('user', JSON.stringify(user));
    return response.data;
  },

  async register(email, password, fullName, role = 'COMPLIANCE_ANALYST') {
    if (isFirebaseConfigured && auth) {
      return this.registerWithFirebaseEmail(email, password, fullName, role);
    }
    const response = await api.post('/auth/register', {
      email,
      password,
      full_name: fullName,
      role,
    });
    const { access_token, user } = response.data;
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('user', JSON.stringify(user));
    return response.data;
  },

  async logout() {
    if (auth) {
      try {
        await firebaseSignOut(auth);
      } catch (e) {
        console.warn('Firebase signout:', e);
      }
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
  },

  async getMe() {
    const response = await api.get('/auth/me');
    return response.data;
  },

  getToken() {
    return localStorage.getItem('access_token');
  },

  getUser() {
    const user = localStorage.getItem('user');
    return user ? JSON.parse(user) : null;
  },

  isAuthenticated() {
    return !!localStorage.getItem('access_token');
  },
};

export default authService;
