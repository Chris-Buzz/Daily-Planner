// ===== Global State =====
const state = {
  tasks: {},
  currentDay: (function(){
    const days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
    const today = new Date();
    return days[today.getDay()];
  })(),
  weekOffset: 0,
  draggedTask: null,
  editingTask: null,
  userSettings: {
    notifications_enabled: false,
    notification_method: 'email',
    email: '',
    phone: '',
    daily_summary: true,
    reminder_time: 30,
    auto_inspiration: true,
    auto_cleanup: false,
    cleanup_weeks: 2,
    auto_delete_old_tasks: false, // Add missing setting
    custom_reminder_times: [300, 60, 30], // Default: 5 hours, 1 hour, 30 minutes (in minutes)
    daily_summary_time: '23:30' // Default: 11:30 PM
  }
};

// ===== DOM Elements =====
const elements = {
  loader: document.getElementById('loader'),
  themeToggle: document.getElementById('theme-toggle'),
  sidebar: document.getElementById('sidebar'),
  sidebarToggle: document.getElementById('sidebar-toggle'),
  daysList: document.getElementById('days-list'),
  currentDayEl: document.getElementById('current-day'),
  currentDateEl: document.getElementById('current-date'),
  taskList: document.getElementById('task-list'),
  completedList: document.getElementById('completed-list'),
  activeCount: document.getElementById('active-count'),
  completedCount: document.getElementById('completed-count'),
  addTaskBtn: document.getElementById('add-task-btn'),
  clearCompletedBtn: document.getElementById('clear-completed'),
  taskModal: document.getElementById('task-modal'),
  taskForm: document.getElementById('task-form'),
  calendarBtn: document.getElementById('calendar-btn'),
  calendarModal: document.getElementById('calendar-modal'),
  calendarGrid: document.getElementById('calendar-grid'),
  calendarMonth: document.getElementById('calendar-month'),
  prevWeekBtn: document.getElementById('prev-week'),
  nextWeekBtn: document.getElementById('next-week'),
  weekLabel: document.getElementById('week-label'),
  notificationContainer: document.getElementById('notification-container'),
  fabAdd: document.getElementById('fab-add'),
  settingsBtn: document.getElementById('settings-btn'),
  settingsModal: document.getElementById('settings-modal'),
  weatherBtn: document.getElementById('weather-btn'),
  weatherModal: document.getElementById('weather-modal'),
  weatherTemp: document.getElementById('weather-temp'),
  fabAssistant: document.getElementById('fab-assistant'),
  assistantPanel: document.getElementById('assistant-panel'),
  assistantClose: document.getElementById('assistant-close'),
  assistantChat: document.getElementById('assistant-chat'),
  assistantInput: document.getElementById('assistant-input'),
  assistantSend: document.getElementById('assistant-send'),
  voiceBtn: document.getElementById('voice-btn')
};

// ===== Utility Functions =====
const utils = {
  generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
  },

  formatTime(time) {
    if (!time) return '';
    
    // Handle time ranges like "19:00-19:30"
    if (time.includes('-')) {
      const [startTime, endTime] = time.split('-');
      return `${this.formatSingleTime(startTime)}-${this.formatSingleTime(endTime)}`;
    }
    
    return this.formatSingleTime(time);
  },
  
  formatSingleTime(time) {
    if (!time) return '';
    const [hour, minute] = time.split(':');
    const h = parseInt(hour, 10);
    const m = parseInt(minute, 10);
    const ampm = h >= 12 ? 'PM' : 'AM';
    const h12 = h % 12 || 12;
    
    // Show minutes only if they're not zero
    if (m === 0) {
      return `${h12} ${ampm}`;
    } else {
      return `${h12}:${minute} ${ampm}`;
    }
  },

  getWeekKey(day) {
    const today = new Date();
    const dayIndex = today.getDay(); // 0=Sunday, 1=Monday, etc.
    const sundayOffset = -dayIndex; // How many days back to Sunday
    const weekStart = new Date(today);
    weekStart.setDate(today.getDate() + sundayOffset + (state.weekOffset * 7));
    
    const year = weekStart.getFullYear();
    const month = (weekStart.getMonth() + 1).toString().padStart(2, '0');
    const date = weekStart.getDate().toString().padStart(2, '0');
    
    return `${year}-${month}-${date}-${day}`;
  },

  getCurrentDate() {
    const today = new Date();
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    return today.toLocaleDateString('en-US', options);
  },

  getWeekDates() {
    const dates = [];
    const today = new Date();
    const dayIndex = today.getDay(); // 0=Sunday, 1=Monday, etc.
    const sundayOffset = -dayIndex; // How many days back to Sunday
    const weekStart = new Date(today);
    weekStart.setDate(today.getDate() + sundayOffset + (state.weekOffset * 7));
    
    for (let i = 0; i < 7; i++) {
      const date = new Date(weekStart);
      date.setDate(weekStart.getDate() + i);
      dates.push(date);
    }
    
    return dates;
  },

  saveToLocalStorage() {
    try {
      localStorage.setItem('dailyPlannerTasks', JSON.stringify(state.tasks));
      localStorage.setItem('dailyPlannerSettings', JSON.stringify(state.userSettings));
      localStorage.setItem('dailyPlannerTheme', document.documentElement.getAttribute('data-theme') || 'light');
    } catch (error) {
      console.error('Error saving to localStorage:', error);
      ui.showNotification('Error saving data', 'error');
    }
  },

  async deleteTaskFromFirebase(taskId) {
    try {
      console.log(`🔍 Attempting to delete task from Firebase: ${taskId}`);
      
      const response = await fetch(`/api/tasks/${taskId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        console.warn(`⚠️ Firebase deletion failed for task ${taskId}, status: ${response.status}`);
        // Don't throw error - task might only exist locally
      } else {
        console.log('✅ Task deleted from Firebase:', taskId);
        // Don't try to parse JSON if response might be empty
      }
      
      // Always remove from local storage regardless of Firebase result
      let taskFound = false;
      for (const weekKey in state.tasks) {
        const initialLength = state.tasks[weekKey].length;
        state.tasks[weekKey] = state.tasks[weekKey].filter(task => task.id !== taskId);
        if (state.tasks[weekKey].length < initialLength) {
          taskFound = true;
          console.log(`🗑️ Removed task ${taskId} from local storage week ${weekKey}`);
        }
      }
      
      if (!taskFound) {
        console.log('⚠️ Task not found in local storage (may have been assistant-created)');
      }
      
      // Save updated local storage
      this.saveToLocalStorage();
      
      return true; // Return true to indicate success
    } catch (error) {
      console.error('Error deleting task from Firebase:', error);
      throw error;
    }
  },

  async bulkDeleteTasksFromFirebase(taskIds) {
    try {
      console.log('bulkDeleteTasksFromFirebase - Starting request with task IDs:', taskIds);
      
      const response = await fetch('/api/tasks/bulk-delete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ task_ids: taskIds })
      });
      
      console.log('bulkDeleteTasksFromFirebase - Response status:', response.status);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('bulkDeleteTasksFromFirebase - Error response:', errorText);
        throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
      }
      
      const result = await response.json();
      console.log('bulkDeleteTasksFromFirebase - Success result:', result);
      console.log(`Bulk deleted ${taskIds.length} tasks from Firebase`);
      return result;
    } catch (error) {
      console.error('Error bulk deleting tasks from Firebase:', error);
      throw error;
    }
  },

  // Refresh tasks from server to sync assistant-created tasks
  async refreshTasksFromFirebase() {
    try {
      console.log('🔄 Refreshing tasks from Firebase...');
      
      // Use makeApiCall for proper authentication and error handling
      const response = await this.makeApiCall('/api/tasks', 'GET');
      
      // Extract tasks from the response format: {"status": "success", "tasks": [...]}
      const firebaseTasks = response.tasks || [];
      console.log('📦 Loaded tasks from Firebase for refresh:', firebaseTasks.length);
      
      // Clear existing tasks and organize by week offset
      state.tasks = {};
      
      firebaseTasks.forEach(task => {
        const weekKey = task.weekOffset || 0;
        if (!state.tasks[weekKey]) {
          state.tasks[weekKey] = [];
        }
        state.tasks[weekKey].push(task);
      });
      
      this.saveToLocalStorage();
      console.log('✅ Tasks refreshed and saved to local storage');
      
      // Update UI
      tasks.render();
      calendar.renderTasks();
      ui.updateUI();
      
      return true;
    } catch (error) {
      console.error('❌ Error refreshing tasks from Firebase:', error);
      return false;
    }
  },

  async loadTasksFromFirebase() {
    try {
      console.log('📥 Loading tasks from Firebase (primary storage)...');
      const response = await fetch('/api/tasks', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        console.log('⚠️ Firebase not available, using local storage fallback');
        return false;
      }
      
      const data = await response.json();
      console.log(`✅ Loaded ${data.tasks ? data.tasks.length : 0} tasks from Firebase`);
      
      if (data.tasks && Array.isArray(data.tasks)) {
        // Clear existing tasks and rebuild from Firebase data
        state.tasks = {};
        
        // Organize tasks by week key
        data.tasks.forEach(task => {
          try {
            // Use weekOffset if available, otherwise calculate from current week
            let weekKey;
            if (task.weekOffset !== undefined) {
              // For tasks with weekOffset, calculate week key based on current week + offset
              const today = new Date();
              const dayIndex = today.getDay();
              const sundayOffset = -dayIndex;
              const weekStart = new Date(today);
              weekStart.setDate(today.getDate() + sundayOffset + (task.weekOffset * 7));
              
              const year = weekStart.getFullYear();
              const month = (weekStart.getMonth() + 1).toString().padStart(2, '0');
              const date = weekStart.getDate().toString().padStart(2, '0');
              weekKey = `${year}-${month}-${date}-${task.day}`;
            } else if (task.preserveWeekPosition && task.absoluteDate) {
              // For class tasks with absolute dates, calculate week key from the actual date
              const taskDate = new Date(task.absoluteDate);
              const dayOfWeek = taskDate.getDay(); // 0=Sunday, 1=Monday, etc.
              const weekStart = new Date(taskDate);
              weekStart.setDate(taskDate.getDate() - dayOfWeek); // Go back to Sunday
              
              const year = weekStart.getFullYear();
              const month = (weekStart.getMonth() + 1).toString().padStart(2, '0');
              const date = weekStart.getDate().toString().padStart(2, '0');
              weekKey = `${year}-${month}-${date}-${task.day}`;
            } else {
              // For tasks without weekOffset or absolute positioning, use current week calculation
              weekKey = this.getWeekKey(task.day);
            }
            
            if (!state.tasks[weekKey]) {
              state.tasks[weekKey] = [];
            }
            
            // Ensure task has required properties
            const processedTask = {
              ...task,
              id: task.id || this.generateId(),
              completed: task.completed || false,
              priority: task.priority || 'medium',
              color: task.color || '#4ECDC4'
            };
            
            state.tasks[weekKey].push(processedTask);
          } catch (error) {
            console.error('⚠️ Error processing task from Firebase:', task, error);
          }
        });
        
        // Backup to local storage after successful Firebase load
        this.saveToLocalStorage();
        console.log('✅ Tasks synchronized from Firebase to local storage backup');
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('❌ Error loading tasks from Firebase:', error);
      console.log('⚠️ Using local storage fallback');
      return false;
    }
  },

  async syncWithFirebase() {
    try {
      console.log('🔄 Performing periodic Firebase sync...');
      await this.loadTasksFromFirebase();
      
      // Update UI after sync
      tasks.render();
      if (elements.calendarModal.classList.contains('active')) {
        calendar.render();
      }
      
      console.log('✅ Periodic Firebase sync completed');
    } catch (error) {
      console.error('⚠️ Periodic Firebase sync failed:', error);
    }
  },

  loadFromLocalStorage() {
    try {
      const savedTasks = localStorage.getItem('dailyPlannerTasks');
      const savedSettings = localStorage.getItem('dailyPlannerSettings');
      const savedTheme = localStorage.getItem('dailyPlannerTheme');
      
      if (savedTasks) {
        state.tasks = JSON.parse(savedTasks);
      }

      if (savedSettings) {
        state.userSettings = { ...state.userSettings, ...JSON.parse(savedSettings) };
      }
      
      if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
      }
    } catch (error) {
      console.error('Error loading from localStorage:', error);
    }
  },

  loadTheme() {
    try {
      // Try localStorage first for immediate theme application
      const savedTheme = localStorage.getItem('dailyPlannerTheme');
      if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
        console.log(`🎨 Theme loaded: ${savedTheme}`);
      } else {
        // Default to light theme
        document.documentElement.setAttribute('data-theme', 'light');
        console.log('🎨 Using default light theme');
      }
    } catch (error) {
      console.error('Error loading theme:', error);
      document.documentElement.setAttribute('data-theme', 'light');
    }
  },

  async saveTheme(theme) {
    try {
      // Save to localStorage immediately
      localStorage.setItem('dailyPlannerTheme', theme);
      
      // Also save to Firebase user settings
      await this.makeApiCall('/api/user-settings', 'POST', { theme: theme });
      console.log(`🎨 Theme saved to Firebase: ${theme}`);
    } catch (error) {
      console.error('⚠️ Failed to save theme to Firebase:', error);
      // Continue with localStorage only
    }
  },

  async makeApiCall(endpoint, method = 'GET', data = null) {
    try {
      const options = {
        method,
        headers: {
          'Content-Type': 'application/json',
        }
      };

      if (data && method !== 'GET') {
        options.body = JSON.stringify(data);
      }

      const response = await fetch(endpoint, options);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('API call failed:', error);
      throw error;
    }
  }
};

// ===== Pattern Detection Helpers =====
// Detect repeated tasks (same title + time) on the same weekday across multiple past weeks
const pattern = {
  // return Date of Sunday for current week adjusted by offset (0=current, 1=next, -1=prev)
  getWeekStartByOffset(offset = 0) {
    const today = new Date();
    const dayIndex = today.getDay(); // 0=Sunday, 1=Monday, etc.
    const sundayOffset = -dayIndex; // How many days back to Sunday
    const weekStart = new Date(today);
    weekStart.setDate(today.getDate() + sundayOffset + (offset * 7));
    weekStart.setHours(0,0,0,0);
    return weekStart;
  },

  // Generate week key exactly like utils.getWeekKey but with custom offset (Sunday-based weeks)
  getWeekKeyWithOffset(day, weekOffset = 0) {
    const today = new Date();
    const dayIndex = today.getDay(); // 0=Sunday, 1=Monday, etc.
    const sundayOffset = -dayIndex; // How many days back to Sunday
    const weekStart = new Date(today);
    weekStart.setDate(today.getDate() + sundayOffset + (weekOffset * 7));
    
    const year = weekStart.getFullYear();
    const month = (weekStart.getMonth() + 1).toString().padStart(2, '0');
    const date = weekStart.getDate().toString().padStart(2, '0');
    
    return `${year}-${month}-${date}-${day}`;
  },





  // analyze last N weeks for repeating title+time signatures
  analyze(weeks = 2, minOccurrences = 2) {
    console.log('Current tasks state:', state.tasks);
    console.log('Current week offset:', state.weekOffset);
    const sigMap = {}; // sig -> { dayCounts: {Monday: count}, samples: [...] }

    // Check the last N weeks (including current week navigation)
    for (let weekBack = 0; weekBack < weeks; weekBack++) {
      const weekOffset = state.weekOffset - weekBack;
      ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'].forEach(day => {
        const key = pattern.getWeekKeyWithOffset(day, weekOffset);
        console.log('Looking for tasks with key:', key, 'for week offset', weekOffset);
        const tasksForDay = state.tasks[key] || [];
        console.log('Found', tasksForDay.length, 'tasks for', key);
        tasksForDay.forEach(t => {
          if (!t.title || !t.time) return;
          const sig = `${t.title.trim().toLowerCase()}||${t.time}`;
          if (!sigMap[sig]) sigMap[sig] = { dayCounts: {}, samples: [] };
          sigMap[sig].dayCounts[day] = (sigMap[sig].dayCounts[day] || 0) + 1;
          sigMap[sig].samples.push({ day: t.day, time: t.time, title: t.title, color: t.color, priority: t.priority, description: t.description });
        });
      });
    }

    const suggestions = [];
    Object.keys(sigMap).forEach(sig => {
      const info = sigMap[sig];
      Object.keys(info.dayCounts).forEach(day => {
        const count = info.dayCounts[day];
        if (count >= minOccurrences) {
          // choose a representative sample
          const sample = info.samples.find(s => s.day === day) || info.samples[0];
          suggestions.push({ title: sample.title, time: sample.time, day, color: sample.color, priority: sample.priority, description: sample.description, occurrences: count });
        }
      });
    });

    return suggestions;
  },

  // populate and show the modal with suggestions
  showSuggestionsIfAny(weeksToScan = 2, minOccurrences = 2) {
    try {
      console.log('Analyzing patterns for', weeksToScan, 'weeks with minimum', minOccurrences, 'occurrences');
      const suggestions = pattern.analyze(weeksToScan, minOccurrences);
      console.log('Found', suggestions.length, 'pattern suggestions:', suggestions);
      if (!suggestions.length) {
        console.log('No pattern suggestions found');
        return;
      }

      const modal = document.getElementById('pattern-modal');
      const list = document.getElementById('pattern-list');
      const weeksSelect = document.getElementById('pattern-weeks');
      list.innerHTML = '';

      suggestions.forEach((s, idx) => {
        const li = document.createElement('li');
        li.style.padding = '0.5rem 0';
        li.innerHTML = `
          <label style="display:flex; align-items:center; gap:0.75rem;">
            <input type="checkbox" class="pattern-check" data-idx="${idx}" checked />
            <div style="flex:1;">${s.title} — ${utils.formatTime(s.time)} on <strong>${s.day}</strong> <span style="color:var(--text-tertiary);">(${s.occurrences}x)</span></div>
          </label>
        `;
        list.appendChild(li);
      });

      // store suggestions on modal for later
      modal._suggestions = suggestions;

      ui.openModal(modal);

      // wire up add selected button
      const addBtn = document.getElementById('pattern-add-selected');
      addBtn.onclick = () => {
        const checked = Array.from(document.querySelectorAll('#pattern-list .pattern-check')).map(ch => ch.checked);
        const weeksToApply = parseInt(weeksSelect.value || '2', 10);
        pattern.applySuggestions(modal._suggestions, checked, weeksToApply);
        ui.closeModal(modal);
      };
    } catch (e) {
      console.error('Pattern suggestion failed', e);
    }
  },

  // apply suggestions into upcoming weeks (avoid duplicates)
  applySuggestions(suggestions = [], checkedArray = [], weeksForward = 2) {
    // for each selected suggestion, for next N weeks (starting next week), create tasks on that weekday if not present
    suggestions.forEach((s, idx) => {
      if (!checkedArray[idx]) return;

      for (let w = 1; w <= weeksForward; w++) {
        const futureWeekOffset = state.weekOffset + w;
        const weekKey = pattern.getWeekKeyWithOffset(s.day, futureWeekOffset);

        if (!state.tasks[weekKey]) state.tasks[weekKey] = [];

        // avoid duplicates: check if same title+time exists
        const exists = state.tasks[weekKey].some(t => (t.title || '').trim().toLowerCase() === (s.title || '').trim().toLowerCase() && t.time === s.time);
        if (!exists) {
          const taskData = { title: s.title, time: s.time, day: s.day, color: s.color || '', priority: s.priority || 'medium', description: s.description || '' };
          // create but bypass UI notification flood: push directly then save once
          const task = {
            id: utils.generateId(),
            title: taskData.title,
            description: taskData.description || '',
            time: taskData.time || '',
            day: taskData.day,
            color: taskData.color || '',
            priority: taskData.priority || 'medium',
            completed: false,
            createdAt: new Date().toISOString()
          };
          state.tasks[weekKey].push(task);
        }
      }
    });

    utils.saveToLocalStorage();
    ui.showNotification('Suggested tasks added to upcoming weeks', 'success');
    // re-render current view and calendar if open
    tasks.render();
    if (elements.calendarModal.classList.contains('active')) calendar.render();
  }
};

// ===== UI Functions =====
const ui = {
  showNotification(message, type = 'info') {
    if (!elements.notificationContainer) {
      const container = document.createElement('div');
      container.className = 'notification-container';
      container.id = 'notification-container';
      document.body.appendChild(container);
      elements.notificationContainer = container;
    }
    
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `<span class="notification-message">${message}</span>`;
    
    elements.notificationContainer.appendChild(notification);
    
    setTimeout(() => {
      notification.style.animation = 'slideOutRight 0.3s ease forwards';
      setTimeout(() => notification.remove(), 300);
    }, 3000);
  },

  updateTaskCounts() {
    const weekKey = utils.getWeekKey(state.currentDay);
    const tasks = state.tasks[weekKey] || [];
    const activeTasks = tasks.filter(t => !t.completed);
    const completedTasks = tasks.filter(t => t.completed);
    
    elements.activeCount.textContent = activeTasks.length;
    elements.completedCount.textContent = completedTasks.length;
    
    // Update day counts in sidebar - use current weekOffset to show correct counts
    const dayItems = elements.daysList.querySelectorAll('.day-item');
    dayItems.forEach(item => {
      const day = item.dataset.day;
      // Use the same week calculation as getWeekKey to match the current view
      const dayKey = utils.getWeekKey(day);
      const dayTasks = state.tasks[dayKey] || [];
      const activeCount = dayTasks.filter(t => !t.completed).length;
      const taskCountEl = item.querySelector('.task-count');
      taskCountEl.textContent = `${activeCount} task${activeCount !== 1 ? 's' : ''}`;
    });
  },

  updateWeekLabel(direction = null) {
    const offset = state.weekOffset;
    let label = 'This Week';
    
    if (offset === -1) label = 'Last Week';
    else if (offset === 1) label = 'Next Week';
    else if (offset < -1) label = `${Math.abs(offset)} Weeks Ago`;
    else if (offset > 1) label = `${offset} Weeks Ahead`;
    
    // Add slide animation if direction is provided
    if (direction && elements.weekLabel) {
      elements.weekLabel.classList.remove('sliding-left', 'sliding-right');
      void elements.weekLabel.offsetWidth; // Force reflow
      elements.weekLabel.classList.add(direction === 'prev' ? 'sliding-left' : 'sliding-right');
    }
    
    setTimeout(() => {
      elements.weekLabel.textContent = label;
    }, direction ? 150 : 0);
  },

  updateCurrentDate() {
    if (elements.currentDateEl) {
      const weekDates = utils.getWeekDates();
      const dayIndex = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'].indexOf(state.currentDay);
      const currentDate = weekDates[dayIndex];
      const options = { month: 'long', day: 'numeric', year: 'numeric' };
      elements.currentDateEl.textContent = currentDate.toLocaleDateString('en-US', options);
    }
  },

  setCurrentDay(day) {
    state.currentDay = day;
    elements.currentDayEl.textContent = day;
    
    // Update active state
    const dayItems = elements.daysList.querySelectorAll('.day-item');
    dayItems.forEach(item => {
      item.classList.toggle('active', item.dataset.day === day);
    });
    
    ui.updateCurrentDate();
    tasks.render();
    
    // Update weather button for selected day
    if (weather.lastWeatherData) {
      weather.updateButtonForSelectedDay(day);
    }
  },

  openModal(modalElement) {
    modalElement.classList.add('active');
    modalElement.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  },

  closeModal(modalElement) {
    modalElement.classList.remove('active');
    modalElement.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  },

  // Custom confirmation modal
  showConfirmation(options = {}) {
    return new Promise((resolve) => {
      const {
        title = 'Confirm Action',
        message = 'Are you sure you want to proceed?',
        confirmText = 'Confirm',
        cancelText = 'Cancel',
        type = 'danger' // danger, warning, info, success
      } = options;

      const modal = document.getElementById('confirmation-modal');
      const titleEl = document.getElementById('confirmation-title');
      const messageEl = document.getElementById('confirmation-message');
      const confirmBtn = document.getElementById('confirmation-confirm');
      const cancelBtn = document.getElementById('confirmation-cancel');
      const confirmTextEl = document.getElementById('confirmation-confirm-text');

      if (!modal) {
        console.error('Confirmation modal not found');
        resolve(false);
        return;
      }

      // Set content
      titleEl.textContent = title;
      messageEl.textContent = message;
      confirmTextEl.textContent = confirmText;
      cancelBtn.querySelector('span').textContent = cancelText;

      // Set type class for styling
      modal.className = `confirmation-modal-overlay ${type}`;

      // Set up icon based on type
      const iconEl = modal.querySelector('.confirmation-icon svg');
      if (type === 'warning') {
        iconEl.innerHTML = '<path d="M1 21h22L12 2 1 21z" stroke="currentColor" stroke-width="2" fill="none"/><line x1="12" y1="9" x2="12" y2="13" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="17" r="1" fill="currentColor"/>';
      } else if (type === 'info') {
        iconEl.innerHTML = '<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" fill="none"/><line x1="12" y1="16" x2="12" y2="12" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="8" r="1" fill="currentColor"/>';
      } else if (type === 'success') {
        iconEl.innerHTML = '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" stroke="currentColor" stroke-width="2" fill="none"/><polyline points="22 4 12 14.01 9 11.01" stroke="currentColor" stroke-width="2" fill="none"/>';
      } else {
        iconEl.innerHTML = '<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" fill="none"/><line x1="9" y1="9" x2="15" y2="15" stroke="currentColor" stroke-width="2"/><line x1="15" y1="9" x2="9" y2="15" stroke="currentColor" stroke-width="2"/>';
      }

      // Event handlers
      const handleConfirm = () => {
        ui.hideConfirmation();
        resolve(true);
      };

      const handleCancel = () => {
        ui.hideConfirmation();
        resolve(false);
      };

      const handleEscape = (e) => {
        if (e.key === 'Escape') {
          handleCancel();
        }
      };

      // Remove existing listeners
      confirmBtn.replaceWith(confirmBtn.cloneNode(true));
      cancelBtn.replaceWith(cancelBtn.cloneNode(true));
      
      // Get new references
      const newConfirmBtn = document.getElementById('confirmation-confirm');
      const newCancelBtn = document.getElementById('confirmation-cancel');

      // Add event listeners
      newConfirmBtn.addEventListener('click', handleConfirm);
      newCancelBtn.addEventListener('click', handleCancel);
      modal.addEventListener('click', (e) => {
        if (e.target === modal) handleCancel();
      });
      document.addEventListener('keydown', handleEscape);

      // Show modal
      modal.classList.add('active');
      
      // Focus on the appropriate button
      setTimeout(() => {
        if (type === 'danger') {
          newCancelBtn.focus();
        } else {
          newConfirmBtn.focus();
        }
      }, 100);

      // Store cleanup function
      modal._cleanup = () => {
        document.removeEventListener('keydown', handleEscape);
      };
    });
  },

  hideConfirmation() {
    const modal = document.getElementById('confirmation-modal');
    if (modal) {
      modal.classList.remove('active');
      if (modal._cleanup) {
        modal._cleanup();
        delete modal._cleanup;
      }
    }
  }
};

// ===== Notification Settings =====
const notifications = {
  async loadSettings() {
    try {
      console.log('🔔 Loading notification settings from Firebase...');
      const settings = await utils.makeApiCall('/api/notification-settings');
      
      if (settings) {
        // Ensure custom reminder times are properly loaded
        state.userSettings = {
          ...state.userSettings,
          ...settings,
          custom_reminder_times: settings.custom_reminder_times || [300, 60, 30],
          daily_summary_time: settings.daily_summary_time || '23:30',
          auto_cleanup: settings.auto_cleanup || settings.auto_delete_old_tasks || false,
          auto_delete_old_tasks: settings.auto_delete_old_tasks || settings.auto_cleanup || false,
          cleanup_weeks: settings.cleanup_weeks || 2
        };
        console.log('✅ Settings loaded from Firebase:', settings);
        
        // Update auto cleanup UI after loading settings
        this.updateAutoCleanupUI();
      }
      
      notifications.updateUI();
    } catch (error) {
      console.error('Failed to load settings:', error);
      // Fall back to local settings
      notifications.updateUI();
    }
  },

  async saveSettings(showNotification = false) {
    try {
      console.log('💾 Starting saveSettings - current custom_reminder_times:', state.userSettings.custom_reminder_times);
      
      // Ensure custom reminder times and daily summary time are included
      const settingsToSave = {
        ...state.userSettings,
        custom_reminder_times: state.userSettings.custom_reminder_times || [300, 60, 30],
        daily_summary_time: state.userSettings.daily_summary_time || '23:30'
      };
      
      console.log('📤 Sending to API:', settingsToSave);
      await utils.makeApiCall('/api/notification-settings', 'POST', settingsToSave);
      utils.saveToLocalStorage();
      console.log('✅ Settings saved successfully to database');
      
      // Only show notification if explicitly requested
      if (showNotification) {
        ui.showNotification('Settings saved successfully!', 'success');
      }
    } catch (error) {
      console.error('❌ Failed to save settings:', error);
      ui.showNotification('Failed to save settings', 'error');
    }
  },

  updateUI() {
    const enabledCheckbox = document.getElementById('notifications-enabled');
    const emailInput = document.getElementById('notification-email');
    const phoneInput = document.getElementById('phone-number');
    const methodCheckboxes = document.querySelectorAll('input[name="notification-methods"]');
    const dailySummaryCheckbox = document.getElementById('daily-summary');
    const reminderTimeSelect = document.getElementById('reminder-time');
    const settingsContent = document.getElementById('settings-content');
    const notificationStatus = document.getElementById('notification-status');

    if (enabledCheckbox) {
      enabledCheckbox.checked = state.userSettings.notifications_enabled;
    }

    // Update status indicator
    if (notificationStatus) {
      const statusIndicator = notificationStatus.querySelector('.status-indicator');
      const statusText = notificationStatus.querySelector('.status-text');
      
      if (statusIndicator && statusText) {
        if (state.userSettings.notifications_enabled) {
          statusIndicator.classList.add('active');
          statusText.textContent = 'Notifications active';
        } else {
          statusIndicator.classList.remove('active');
          statusText.textContent = 'Notifications disabled';
        }
      }
    }

    if (emailInput) {
      emailInput.value = state.userSettings.email || '';
    }

    if (phoneInput) {
      phoneInput.value = state.userSettings.phone || '';
    }

    // Handle multiple notification methods
    if (methodCheckboxes.length > 0) {
      const selectedMethods = state.userSettings.notification_methods || [state.userSettings.notification_method || 'email'];
      
      methodCheckboxes.forEach(checkbox => {
        checkbox.checked = selectedMethods.includes(checkbox.value);
      });
    }

    if (dailySummaryCheckbox) {
      dailySummaryCheckbox.checked = state.userSettings.daily_summary !== false;
    }

    if (reminderTimeSelect) {
      reminderTimeSelect.value = state.userSettings.reminder_time || 30;
    }

    const autoInspirationCheckbox = document.getElementById('auto-inspiration');
    if (autoInspirationCheckbox) {
      autoInspirationCheckbox.checked = state.userSettings.auto_inspiration !== false;
    }

    // Initialize cleanup settings - will be updated after loading from database
    const autoCleanupCheckbox = document.getElementById('auto-cleanup');
    const cleanupWeeksSetting = document.getElementById('cleanup-weeks-setting');
    const cleanupWeeksSelect = document.getElementById('cleanup-weeks');
    
    // Note: Actual values will be set by notifications.updateAutoCleanupUI() after loading from database

    // Show/hide settings content
    if (settingsContent) {
      settingsContent.style.display = state.userSettings.notifications_enabled ? 'block' : 'none';
    }
    
    // Initialize custom reminder times UI
    this.renderCustomReminderTimes();
    
    // Initialize daily summary time UI
    const dailySummaryTimeInput = document.getElementById('daily-summary-time');
    if (dailySummaryTimeInput && state.userSettings.daily_summary_time) {
      dailySummaryTimeInput.value = state.userSettings.daily_summary_time;
    }
  },

  // Render custom reminder times in the UI
  renderCustomReminderTimes() {
    console.log('🔔 Rendering custom reminder times...');
    const reminderTimesList = document.getElementById('reminder-times-list');
    if (!reminderTimesList) {
      console.error('❌ Element #reminder-times-list not found!');
      return;
    }
    
    console.log('📝 Custom reminder times:', state.userSettings.custom_reminder_times);
    
    reminderTimesList.innerHTML = '';
    
    if (!state.userSettings.custom_reminder_times || state.userSettings.custom_reminder_times.length === 0) {
      // Show empty state
      reminderTimesList.innerHTML = `
        <div class="reminder-times-empty">
          <div class="reminder-times-empty-icon">⏰</div>
          <h6>No reminder times set</h6>
          <p>Click "Add Reminder" to set when you want to be notified before your tasks are due.</p>
        </div>
      `;
      return;
    }
    
    state.userSettings.custom_reminder_times.forEach((minutes, index) => {
      const reminderItem = document.createElement('div');
      reminderItem.className = 'reminder-time-item';
      reminderItem.innerHTML = `
        <div class="reminder-time-info">
          <div class="reminder-time-icon">🔔</div>
          <div class="reminder-time-details">
            <div class="reminder-time-label">${this.formatReminderTime(minutes)}</div>
            <div class="reminder-time-description">Notify ${this.formatReminderTime(minutes).toLowerCase()} before tasks are due</div>
          </div>
        </div>
        <div class="reminder-time-input">
          <input type="number" value="${this.getTimeValue(minutes)}" min="1" max="9999" 
                 onchange="notifications.updateReminderTime(${index}, this.value, '${this.getTimeUnit(minutes)}')">
          <select onchange="notifications.updateReminderTime(${index}, '${this.getTimeValue(minutes)}', this.value)">
            <option value="minutes" ${this.getTimeUnit(minutes) === 'minutes' ? 'selected' : ''}>Minutes</option>
            <option value="hours" ${this.getTimeUnit(minutes) === 'hours' ? 'selected' : ''}>Hours</option>
            <option value="days" ${this.getTimeUnit(minutes) === 'days' ? 'selected' : ''}>Days</option>
          </select>
        </div>
        <button class="remove-reminder-btn" onclick="notifications.removeReminderTime(${index})" 
                title="Remove this reminder time">
          <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
            <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z"/>
            <path fill-rule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"/>
          </svg>
        </button>
      `;
      reminderTimesList.appendChild(reminderItem);
    });
  },

  // Helper functions for time conversion
  getTimeValue(minutes) {
    if (minutes >= 1440) { // 1 day or more
      return Math.floor(minutes / 1440);
    } else if (minutes >= 60) { // 1 hour or more
      return Math.floor(minutes / 60);
    } else {
      return minutes;
    }
  },

  getTimeUnit(minutes) {
    if (minutes >= 1440) {
      return 'days';
    } else if (minutes >= 60) {
      return 'hours';
    } else {
      return 'minutes';
    }
  },

  convertToMinutes(value, unit) {
    const num = parseInt(value);
    switch (unit) {
      case 'hours':
        return num * 60;
      case 'days':
        return num * 1440;
      default:
        return num;
    }
  },

  // Reminder time management functions
  async addQuickReminderTime(minutes) {
    if (!state.userSettings.custom_reminder_times) {
      state.userSettings.custom_reminder_times = [];
    }
    
    // Check if this time already exists
    if (!state.userSettings.custom_reminder_times.includes(minutes)) {
      state.userSettings.custom_reminder_times.push(minutes);
      state.userSettings.custom_reminder_times.sort((a, b) => b - a); // Sort descending
      
      // Save to database immediately and wait for completion (no generic save notification)
      await this.saveSettings(false);
      this.renderCustomReminderTimes();
      
      ui.showNotification(`Added ${this.formatReminderTime(minutes)} reminder`, 'success');
    } else {
      ui.showNotification(`${this.formatReminderTime(minutes)} reminder already exists`, 'info');
    }
    
    // Hide the add reminder menu
    const menu = document.querySelector('.add-reminder-menu');
    if (menu) {
      menu.classList.remove('active');
    }
  },

  addCustomReminderTime() {
    const valueInput = document.getElementById('custom-reminder-value');
    const unitSelect = document.getElementById('custom-reminder-unit');
    
    if (!valueInput || !unitSelect) return;
    
    const value = parseInt(valueInput.value);
    const unit = unitSelect.value;
    
    if (!value || value <= 0) {
      ui.showNotification('Please enter a valid time value', 'error');
      return;
    }
    
    const minutes = this.convertToMinutes(value, unit);
    this.addQuickReminderTime(minutes);
    
    // Reset form
    valueInput.value = '';
    unitSelect.value = 'minutes';
  },

  async updateReminderTime(index, value, unit) {
    const minutes = this.convertToMinutes(value, unit);
    
    if (minutes <= 0) {
      ui.showNotification('Please enter a valid time value', 'error');
      this.renderCustomReminderTimes(); // Reset the UI
      return;
    }
    
    const oldTime = this.formatReminderTime(state.userSettings.custom_reminder_times[index]);
    state.userSettings.custom_reminder_times[index] = minutes;
    state.userSettings.custom_reminder_times.sort((a, b) => b - a); // Sort descending
    
    // Save to database immediately and wait for completion (no generic save notification)
    await this.saveSettings(false);
    this.renderCustomReminderTimes();
    
    ui.showNotification(`Updated reminder time to ${this.formatReminderTime(minutes)}`, 'success');
  },

  async removeReminderTime(index) {
    console.log('🗑️ Removing reminder time at index:', index);
    const removedTime = this.formatReminderTime(state.userSettings.custom_reminder_times[index]);
    state.userSettings.custom_reminder_times.splice(index, 1);
    
    console.log('💾 Saving updated reminder times to database...', state.userSettings.custom_reminder_times);
    
    // Save to database immediately and wait for completion (no notification)
    await this.saveSettings(false);
    this.renderCustomReminderTimes();
    
    ui.showNotification(`Removed ${removedTime} reminder`, 'success');
  },

  // Update auto cleanup UI elements when settings are loaded
  updateAutoCleanupUI() {
    const autoCleanupCheckbox = document.getElementById('auto-cleanup');
    const cleanupWeeksSetting = document.getElementById('cleanup-weeks-setting');
    const cleanupWeeksSelect = document.getElementById('cleanup-weeks');
    
    if (autoCleanupCheckbox) {
      const isEnabled = state.userSettings.auto_cleanup || state.userSettings.auto_delete_old_tasks || false;
      autoCleanupCheckbox.checked = isEnabled;
      console.log('🗑️ Auto cleanup checkbox updated:', isEnabled);
    }
    
    if (cleanupWeeksSetting) {
      const isEnabled = state.userSettings.auto_cleanup || state.userSettings.auto_delete_old_tasks || false;
      cleanupWeeksSetting.style.display = isEnabled ? 'flex' : 'none';
    }
    
    if (cleanupWeeksSelect) {
      cleanupWeeksSelect.value = state.userSettings.cleanup_weeks || 2;
    }
  },

  // Format time from 24-hour to 12-hour format for user display
  formatTimeForDisplay(time24) {
    const [hours, minutes] = time24.split(':');
    const hour12 = parseInt(hours) % 12 || 12;
    const ampm = parseInt(hours) >= 12 ? 'PM' : 'AM';
    return `${hour12}:${minutes} ${ampm}`;
  },

  async updateDailySummaryTime() {
    const timeInput = document.getElementById('daily-summary-time');
    if (timeInput) {
      state.userSettings.daily_summary_time = timeInput.value;
      
      // Save to database immediately and wait for completion (no generic save notification)
      await this.saveSettings(false);
      
      ui.showNotification(`Daily summary time updated to ${this.formatTimeForDisplay(timeInput.value)}`, 'success');
    }
  },

  // Format reminder time for display
  formatReminderTime(minutes) {
    if (minutes >= 1440) {
      const days = Math.floor(minutes / 1440);
      const remainingHours = Math.floor((minutes % 1440) / 60);
      const remainingMinutes = minutes % 60;
      
      if (remainingHours === 0 && remainingMinutes === 0) {
        return days === 1 ? '1 day' : `${days} days`;
      } else if (remainingMinutes === 0) {
        return `${days}d ${remainingHours}h`;
      } else {
        return `${days}d ${remainingHours}h ${remainingMinutes}m`;
      }
    } else if (minutes >= 60) {
      const hours = Math.floor(minutes / 60);
      const remainingMinutes = minutes % 60;
      
      if (remainingMinutes === 0) {
        return hours === 1 ? '1 hour' : `${hours} hours`;
      } else {
        return `${hours}h ${remainingMinutes}m`;
      }
    } else {
      return minutes === 1 ? '1 minute' : `${minutes} minutes`;
    }
  },

  // Toggle add reminder menu
  toggleAddReminderMenu() {
    const menu = document.querySelector('.add-reminder-menu');
    if (menu) {
      menu.classList.toggle('active');
    }
  },

  async sendTestNotification() {
    try {
      console.log('🧪 Sending test notification...');
      ui.showNotification('Sending test notification...', 'info');
      
      const response = await utils.makeApiCall('/api/test-notification', 'POST');
      
      if (response.status === 'success') {
        ui.showNotification(response.message, 'success');
        console.log('✅ Test notification sent successfully');
      } else {
        ui.showNotification('Test notification sent!', 'success');
      }
    } catch (error) {
      console.error('❌ Failed to send test notification:', error);
      
      // Show specific error message if available
      const errorMessage = error.response?.error || error.message || 'Failed to send test notification';
      ui.showNotification(errorMessage, 'error');
    }
  },
  
  async sendInspiration() {
    try {
      console.log('💫 Sending inspiration message...');
      const response = await utils.makeApiCall('/api/send-inspiration', 'POST');
      
      if (response.message) {
        const messageDiv = document.getElementById('inspiration-message');
        if (messageDiv) {
          messageDiv.textContent = response.message;
          messageDiv.style.display = 'block';
          setTimeout(() => {
            messageDiv.style.display = 'none';
          }, 5000);
        }
        ui.showNotification('Inspiration sent!', 'success');
      }
    } catch (error) {
      console.error('❌ Failed to send inspiration:', error);
      ui.showNotification('Failed to send inspiration message', 'error');
    }
  }
};

// ===== Task Management =====
const tasks = {
  async create(taskData) {
    const task = {
      id: utils.generateId(),
      title: taskData.title || 'Untitled Task',
      description: taskData.description || '',
      time: taskData.time || '',
      startTime: taskData.startTime || '',
      endTime: taskData.endTime || '',
      day: taskData.day,
      color: taskData.color || '',
      priority: taskData.priority || 'medium',
      completed: false,
      createdAt: new Date().toISOString(),
      weekOffset: taskData.weekOffset || 0
    };
    
    try {
      // Save to Firebase FIRST (primary storage)
      console.log('📤 Saving task to Firebase (primary storage):', task.title);
      const result = await utils.makeApiCall('/api/tasks', 'POST', task);
      
      // Update task with Firebase ID if different
      if (result.id && result.id !== task.id) {
        console.log(`🔄 Updating task ID from ${task.id} to ${result.id}`);
        task.id = result.id;
      }
      
      console.log('✅ Task saved to Firebase successfully');
    } catch (error) {
      console.error('❌ Failed to save task to Firebase:', error);
      // For critical operations, we should not continue without Firebase
      ui.showNotification('Failed to save task to database. Please check your connection.', 'error');
      throw error;
    }
    
    // Save to local storage as backup after successful Firebase save
    try {
      const weekKey = utils.getWeekKey(taskData.day);
      if (!state.tasks[weekKey]) {
        state.tasks[weekKey] = [];
      }
      state.tasks[weekKey].push(task);
      utils.saveToLocalStorage();
      console.log('✅ Task backed up to local storage');
    } catch (error) {
      console.error('⚠️ Failed to backup task to local storage:', error);
      // This is less critical since Firebase is our primary storage
    }
    
    ui.showNotification('Task created successfully', 'success');
    
    // Schedule notifications for the new task
    if (state.userSettings.notifications_enabled) {
      notificationScheduler.onTaskCreated(task);
    }
    
    return task;
  },

  async createWithWeekOffset(taskData) {
    const task = {
      id: taskData.id || utils.generateId(), // Use provided ID if available (prevents duplicates)
      title: taskData.title || 'Untitled Task',
      description: taskData.description || '',
      time: taskData.time || '',
      startTime: taskData.startTime || '',
      endTime: taskData.endTime || '',
      day: taskData.day,
      color: taskData.color || '',
      priority: taskData.priority || 'medium',
      completed: false,
      createdAt: new Date().toISOString(),
      weekOffset: taskData.weekOffset || 0,
      createdBy: taskData.createdBy || 'user'
    };
    
    console.log(`🔄 Creating task with ID: ${task.id}, Title: ${task.title}, CreatedBy: ${task.createdBy}`);
    
    try {
      // Save to Firebase FIRST (primary storage)
      console.log(`📤 Sending task to Firebase: ${task.id} - ${task.title}`);
      const result = await utils.makeApiCall('/api/tasks', 'POST', task);
      console.log(`✅ Task with week offset saved to database successfully - Firebase ID: ${result.id || 'N/A'}`);
      
      // Update task with Firebase ID if it was generated server-side
      if (result.id && result.id !== task.id) {
        console.log(`🔄 Updating task ID from ${task.id} to ${result.id}`);
        task.id = result.id;
      }
    } catch (error) {
      console.error('⚠️ Failed to save week offset task to database:', error);
      // For assistant tasks, this is more critical, so we should fail
      if (taskData.createdBy === 'assistant') {
        throw error; // Re-throw for assistant tasks to handle properly
      }
      // For user tasks, we can continue with local storage only as fallback
      console.log('⚠️ Continuing with local storage only (offline mode)');
    }
    
    // Save to local storage as backup after Firebase attempt
    try {
      const weekKey = pattern.getWeekKeyWithOffset(taskData.day, taskData.weekOffset || 0);
      if (!state.tasks[weekKey]) {
        state.tasks[weekKey] = [];
      }
      state.tasks[weekKey].push(task);
      utils.saveToLocalStorage();
      console.log('✅ Task backed up to local storage');
    } catch (error) {
      console.error('⚠️ Failed to backup task to local storage:', error);
    }
    
    // Show notification with week context (only for user-created tasks)
    if (taskData.createdBy !== 'assistant') {
      const weekInfo = taskData.weekOffset === 0 ? 'this week' : 
                       taskData.weekOffset === 1 ? 'next week' : 
                       `${taskData.weekOffset} weeks ahead`;
      ui.showNotification(`Task created for ${weekInfo}`, 'success');
    }
    
    return task;
  },

  async update(taskId, updates) {
    try {
      // Update in Firebase FIRST (primary storage)
      console.log(`🔄 Updating task ${taskId} in Firebase...`);
      await utils.makeApiCall(`/api/tasks/${taskId}`, 'PUT', updates);
      console.log('✅ Task updated in Firebase successfully');
      
      // Find the task in local storage and update it
      let taskFound = false;
      let oldWeekKey = null;
      let taskIndex = -1;
      
      // Find which week the task is currently in
      for (const weekKey in state.tasks) {
        taskIndex = state.tasks[weekKey].findIndex(t => t.id === taskId);
        if (taskIndex !== -1) {
          oldWeekKey = weekKey;
          taskFound = true;
          break;
        }
      }
      
      if (taskFound) {
        const oldTask = state.tasks[oldWeekKey][taskIndex];
        const updatedTask = {
          ...oldTask,
          ...updates,
          updatedAt: new Date().toISOString()
        };
        
        // Check if the day changed - if so, move to correct week
        if (updates.day && updates.day !== oldTask.day) {
          const newWeekKey = utils.getWeekKey(updates.day);
          
          // Remove from old week
          state.tasks[oldWeekKey].splice(taskIndex, 1);
          
          // Add to new week
          if (!state.tasks[newWeekKey]) {
            state.tasks[newWeekKey] = [];
          }
          state.tasks[newWeekKey].push(updatedTask);
          
          console.log(`✅ Task moved from ${oldWeekKey} to ${newWeekKey}`);
        } else {
          // Day didn't change, just update in place
          state.tasks[oldWeekKey][taskIndex] = updatedTask;
        }
        
        utils.saveToLocalStorage();
        console.log('✅ Task updated in local storage backup');
        
        // Update notifications for the task
        if (state.userSettings.notifications_enabled) {
          notificationScheduler.onTaskUpdated(updatedTask);
        }
      }
      
      ui.showNotification('Task updated', 'success');
      return true;
    } catch (error) {
      console.error('❌ Failed to update task in Firebase:', error);
      
      // Fallback: update local storage only
      for (const weekKey in state.tasks) {
        const taskIndex = state.tasks[weekKey].findIndex(t => t.id === taskId);
        if (taskIndex !== -1) {
          state.tasks[weekKey][taskIndex] = {
            ...state.tasks[weekKey][taskIndex],
            ...updates,
            updatedAt: new Date().toISOString()
          };
          utils.saveToLocalStorage();
          ui.showNotification('Task updated locally (sync failed)', 'warning');
          return true;
        }
      }
      
      ui.showNotification('Failed to update task', 'error');
      return false;
    }
  },

  async delete(taskId) {
    let taskFound = false;
    
    // Check if task exists in local storage first
    for (const weekKey in state.tasks) {
      const taskIndex = state.tasks[weekKey].findIndex(t => t.id === taskId);
      if (taskIndex !== -1) {
        taskFound = true;
        break;
      }
    }
    
    if (!taskFound) {
      console.log(`⚠️ Task ${taskId} not found in local storage`);
      ui.showNotification('Task not found', 'warning');
      return false;
    }
    
    try {
      if (taskId) {
        console.log(`🔍 Deleting task ${taskId}...`);
        // deleteTaskFromFirebase already handles both Firebase and local storage deletion
        await utils.deleteTaskFromFirebase(taskId);
        console.log(`✅ Task ${taskId} deleted successfully`);
      } else {
        console.log('❌ No task ID provided for deletion');
        return false;
      }
      
      // Update UI immediately
      tasks.render();
      
      // Re-render calendar if it's open
      if (elements.calendarModal.classList.contains('active')) {
        calendar.render();
      }
      
      ui.showNotification('Task deleted', 'success');
      return true;
    } catch (error) {
      console.error('Error deleting task:', error);
      
      // Even if Firebase deletion failed, try to remove from local storage as fallback
      for (const weekKey in state.tasks) {
        const taskIndex = state.tasks[weekKey].findIndex(t => t.id === taskId);
        if (taskIndex !== -1) {
          state.tasks[weekKey].splice(taskIndex, 1);
          console.log(`🔄 Removed task ${taskId} from local storage as fallback`);
          break;
        }
      }
      utils.saveToLocalStorage();
      
      // Update UI even after fallback deletion
      tasks.render();
      if (elements.calendarModal.classList.contains('active')) {
        calendar.render();
      }
      
      ui.showNotification('Task deleted (locally)', 'warning');
      return true; // Return true since we did delete it locally
    }
  },

  async toggleComplete(taskId) {
    for (const weekKey in state.tasks) {
      const task = state.tasks[weekKey].find(t => t.id === taskId);
      if (task) {
        const newCompletedState = !task.completed;
        const updateData = {
          completed: newCompletedState,
          completedAt: newCompletedState ? new Date().toISOString() : undefined
        };
        
        try {
          // Update in Firebase FIRST (primary storage)
          console.log(`🔄 Updating task completion in Firebase: ${taskId}`);
          await utils.makeApiCall(`/api/tasks/${task.id}`, 'PUT', updateData);
          console.log('✅ Task completion status updated in Firebase');
          
          // Update local storage as backup after successful Firebase update
          task.completed = newCompletedState;
          if (newCompletedState) {
            task.completedAt = updateData.completedAt;
            // Clear notifications when task is completed
            if (state.userSettings.notifications_enabled) {
              notificationScheduler.onTaskCompleted(taskId);
            }
          } else {
            delete task.completedAt;
            // Reschedule notifications when task is reopened
            if (state.userSettings.notifications_enabled) {
              notificationScheduler.onTaskUpdated(task);
            }
          }
          utils.saveToLocalStorage();
          console.log('✅ Task completion backed up to local storage');
          
          // Immediately update UI after successful completion
          tasks.render();
          if (elements.calendarModal.classList.contains('active')) {
            calendar.render();
          }
          
        } catch (error) {
          console.error('⚠️ Failed to update task completion in Firebase:', error);
          // Fallback: update local storage only
          task.completed = newCompletedState;
          if (newCompletedState) {
            task.completedAt = updateData.completedAt;
          } else {
            delete task.completedAt;
          }
          utils.saveToLocalStorage();
          ui.showNotification('Task updated locally (sync failed)', 'warning');
          
          // Immediately update UI after fallback completion
          tasks.render();
          if (elements.calendarModal.classList.contains('active')) {
            calendar.render();
          }
        }
        
        ui.showNotification(task.completed ? 'Task completed!' : 'Task reopened', 'success');
        return true;
      }
    }
    return false;
  },

  async clearCompleted() {
    const weekKey = utils.getWeekKey(state.currentDay);
    if (state.tasks[weekKey]) {
      const completedTasks = state.tasks[weekKey].filter(t => t.completed);
      const clearedCount = completedTasks.length;
      
      if (clearedCount > 0) {
        try {
          // Show loading state
          ui.showNotification('Clearing completed tasks...', 'info');
          
          // Get task IDs for Firebase deletion
          const taskIds = completedTasks.map(task => task.id).filter(id => id);
          
          // Delete from Firebase first (if there are task IDs)
          if (taskIds.length > 0) {
            await utils.bulkDeleteTasksFromFirebase(taskIds);
          }
          
          // Delete from local state
          state.tasks[weekKey] = state.tasks[weekKey].filter(t => !t.completed);
          utils.saveToLocalStorage();
          
          // Update UI immediately
          tasks.render();
          
          // Re-render calendar if it's open
          if (elements.calendarModal.classList.contains('active')) {
            calendar.render();
          }
          
          ui.showNotification(`Cleared ${clearedCount} completed task${clearedCount !== 1 ? 's' : ''}`, 'success');
        } catch (error) {
          console.error('Error clearing completed tasks from Firebase:', error);
          
          // Still clear locally as fallback
          state.tasks[weekKey] = state.tasks[weekKey].filter(t => !t.completed);
          utils.saveToLocalStorage();
          
          // Update UI immediately
          tasks.render();
          
          // Re-render calendar if it's open
          if (elements.calendarModal.classList.contains('active')) {
            calendar.render();
          }
          
          ui.showNotification(`Cleared ${clearedCount} completed task${clearedCount !== 1 ? 's' : ''} (server sync failed)`, 'warning');
        }
      } else {
        ui.showNotification('No completed tasks to clear', 'info');
      }
    }
  },

  async deleteAllToday() {
    const weekKey = utils.getWeekKey(state.currentDay);
    if (state.tasks[weekKey] && state.tasks[weekKey].length > 0) {
      const tasksToDelete = [...state.tasks[weekKey]]; // Copy the tasks before deletion
      const taskCount = tasksToDelete.length;
      const dayName = state.currentDay;
      
      const confirmed = await ui.showConfirmation({
        title: 'Delete All Tasks',
        message: `Are you sure you want to delete all ${taskCount} task${taskCount !== 1 ? 's' : ''} for ${dayName}? This action cannot be undone.`,
        confirmText: 'Delete All',
        cancelText: 'Cancel',
        type: 'danger'
      });
      
      if (confirmed) {
        try {
          // Show loading state
          ui.showNotification('Deleting tasks...', 'info');
          
          // Get task IDs for Firebase deletion
          console.log('Delete All Today - All tasks:', tasksToDelete.map(task => ({ 
            title: task.title, 
            id: task.id, 
            hasId: !!task.id 
          })));
          
          const taskIds = tasksToDelete.map(task => task.id).filter(id => id);
          const tasksWithoutIds = tasksToDelete.filter(task => !task.id);
          
          console.log('Delete All Today - Tasks to delete:', tasksToDelete.length);
          console.log('Delete All Today - Task IDs found:', taskIds.length, taskIds);
          console.log('Delete All Today - Tasks without IDs:', tasksWithoutIds.length, tasksWithoutIds.map(t => t.title));
          
          // Delete from Firebase first (if there are task IDs)
          if (taskIds.length > 0) {
            console.log('Calling bulkDeleteTasksFromFirebase with IDs:', taskIds);
            await utils.bulkDeleteTasksFromFirebase(taskIds);
            console.log('Firebase bulk delete completed successfully');
          } else {
            console.log('No task IDs found - skipping Firebase deletion');
          }
          
          // Delete from local state
          state.tasks[weekKey] = [];
          utils.saveToLocalStorage();
          
          ui.showNotification(`Deleted all ${taskCount} task${taskCount !== 1 ? 's' : ''} for ${dayName}`, 'success');
          tasks.render();
          
          // Re-render calendar if it's open
          if (elements.calendarModal.classList.contains('active')) {
            calendar.render();
          }
        } catch (error) {
          console.error('Error deleting tasks:', error);
          ui.showNotification('Some tasks may not have been deleted from the server. Please refresh and try again.', 'warning');
          
          // Still delete locally as fallback
          state.tasks[weekKey] = [];
          utils.saveToLocalStorage();
          tasks.render();
          
          if (elements.calendarModal.classList.contains('active')) {
            calendar.render();
          }
        }
      }
    } else {
      ui.showNotification(`No tasks to delete for ${state.currentDay}`, 'info');
    }
  },

  deleteOldTasks() {
    // Check both field names for compatibility
    if (!state.userSettings.auto_cleanup && !state.userSettings.auto_delete_old_tasks) return;
    
    const oneWeekAgo = new Date();
    oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
    
    let deletedCount = 0;
    const keysToDelete = [];
    
    Object.keys(state.tasks).forEach(weekKey => {
      try {
        // Parse the week key format: YYYY-MM-DD-Day
        const datePart = weekKey.split('-').slice(0, 3).join('-'); // Get YYYY-MM-DD
        const taskDate = new Date(datePart);
        
        if (taskDate < oneWeekAgo) {
          deletedCount += state.tasks[weekKey].length;
          keysToDelete.push(weekKey);
        }
      } catch (e) {
        console.warn('Could not parse date from week key:', weekKey);
      }
    });
    
    // Delete old task groups
    keysToDelete.forEach(key => {
      delete state.tasks[key];
    });
    
    if (deletedCount > 0) {
      utils.saveToLocalStorage();
      console.log(`Auto-deleted ${deletedCount} old tasks from ${keysToDelete.length} days`);
    }
  },

  render() {
    const weekKey = utils.getWeekKey(state.currentDay);
    const dayTasks = state.tasks[weekKey] || [];
    
    // Sort tasks: uncompleted first, then by priority and time
    const sortedTasks = [...dayTasks].sort((a, b) => {
      if (a.completed !== b.completed) return a.completed ? 1 : -1;
      
      const priorityOrder = { high: 0, medium: 1, low: 2 };
      if (a.priority !== b.priority) {
        return priorityOrder[a.priority] - priorityOrder[b.priority];
      }
      
      if (a.time && b.time) return a.time.localeCompare(b.time);
      if (a.time) return -1;
      if (b.time) return 1;
      
      return 0;
    });
    
    const activeTasks = sortedTasks.filter(t => !t.completed);
    const completedTasks = sortedTasks.filter(t => t.completed);
    
    elements.taskList.innerHTML = '';
    elements.completedList.innerHTML = '';
    
    activeTasks.forEach(task => {
      elements.taskList.appendChild(tasks.createTaskElement(task));
    });
    
    completedTasks.forEach(task => {
      elements.completedList.appendChild(tasks.createTaskElement(task));
    });
    
    ui.updateTaskCounts();
  },

  createTaskElement(task) {
    const li = document.createElement('li');
    li.className = 'task-item';
    li.draggable = !task.completed;
    li.dataset.taskId = task.id;
    li.style.setProperty('--task-color', task.color || 'transparent');
    
    if (task.completed) {
      li.classList.add('completed');
    }
    
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'task-checkbox';
    checkbox.checked = task.completed;
    checkbox.addEventListener('change', async () => {
      await tasks.toggleComplete(task.id);
    });
    
    const content = document.createElement('div');
    content.className = 'task-content';
    
    const header = document.createElement('div');
    header.className = 'task-header';
    
    const title = document.createElement('div');
    title.className = 'task-title';
    title.textContent = task.title;
    
    const meta = document.createElement('div');
    meta.className = 'task-meta';
    
    if (task.time) {
      const time = document.createElement('span');
      time.className = 'task-time';
      // Show both start and end time for class tasks, just start time for regular tasks
      if (task.isClassTask && task.endTime) {
        time.innerHTML = `<svg viewBox="0 0 24 24" width="14" height="14"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" fill="none"/><polyline points="12 6 12 12 16 14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/></svg>${utils.formatTime(task.time)} - ${utils.formatTime(task.endTime)}`;
      } else {
        time.innerHTML = `<svg viewBox="0 0 24 24" width="14" height="14"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" fill="none"/><polyline points="12 6 12 12 16 14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/></svg>${utils.formatTime(task.time)}`;
      }
      meta.appendChild(time);
    }
    
    if (task.priority && task.priority !== 'medium') {
      const priority = document.createElement('span');
      priority.className = `task-priority ${task.priority}`;
      priority.textContent = task.priority;
      meta.appendChild(priority);
    }
    
    header.appendChild(title);
    header.appendChild(meta);
    content.appendChild(header);
    
    if (task.description) {
      const desc = document.createElement('div');
      desc.className = 'task-description';
      desc.textContent = task.description;
      content.appendChild(desc);
    }
    
    const actions = document.createElement('div');
    actions.className = 'task-actions';
    
    if (!task.completed) {
      const editBtn = document.createElement('button');
      editBtn.className = 'task-action-btn';
      editBtn.textContent = 'Edit';
      editBtn.addEventListener('click', () => tasks.showEditForm(task));
      actions.appendChild(editBtn);
    }
    
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'task-action-btn delete';
    deleteBtn.textContent = task.completed ? '×' : 'Delete';
    deleteBtn.style.fontWeight = task.completed ? 'bold' : 'normal';
    deleteBtn.style.fontSize = task.completed ? '1.2rem' : '0.75rem';
    deleteBtn.addEventListener('click', async () => {
      const confirmed = await ui.showConfirmation({
        title: 'Delete Task',
        message: 'Are you sure you want to delete this task? This action cannot be undone.',
        confirmText: 'Delete',
        cancelText: 'Cancel',
        type: 'danger'
      });
      
      if (confirmed) {
        tasks.delete(task.id);
        tasks.render();
        if (elements.calendarModal.classList.contains('active')) {
          calendar.render();
        }
      }
    });
    actions.appendChild(deleteBtn);
    
    content.appendChild(actions);
    
    li.appendChild(checkbox);
    li.appendChild(content);
    
    // Drag and drop
    if (!task.completed) {
      li.addEventListener('dragstart', (e) => {
        state.draggedTask = task;
        li.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
      });
      
      li.addEventListener('dragend', () => {
        li.classList.remove('dragging');
        state.draggedTask = null;
      });
    }
    
    return li;
  },

  showEditForm(task) {
    state.editingTask = task;
    
    // Populate form
    document.getElementById('task-title').value = task.title;
    document.getElementById('task-description').value = task.description;
    
    // Handle time fields
    const startTimeField = document.getElementById('task-start-time');
    const endTimeField = document.getElementById('task-end-time');
    
    if (startTimeField) startTimeField.value = task.startTime || '';
    if (endTimeField) endTimeField.value = task.endTime || '';
    
    // Fallback for old time field if it exists
    const oldTimeField = document.getElementById('task-time');
    if (oldTimeField && task.time) {
      oldTimeField.value = task.time;
    }
    
    // Set the day checkboxes - when editing, only check the task's day
    const dayCheckboxes = document.querySelectorAll('input[name="days"]');
    dayCheckboxes.forEach(checkbox => {
      checkbox.checked = checkbox.value === task.day;
    });
    
    document.getElementById('task-priority').value = task.priority;
    
    // Set color
    const colorRadios = document.querySelectorAll('input[name="color"]');
    colorRadios.forEach(radio => {
      radio.checked = radio.value === task.color;
    });
    
    // Update modal title and button
    const modalHeader = elements.taskModal.querySelector('.modal-header h2');
    modalHeader.textContent = 'Edit Task';
    
    const submitBtn = elements.taskForm.querySelector('button[type="submit"]');
    submitBtn.textContent = 'Update Task';
    
    ui.openModal(elements.taskModal);
  }
};

// ===== Calendar Functions =====
const calendar = {
  render() {
    const grid = elements.calendarGrid;
    grid.innerHTML = '';
    
    // Update month display
    const weekDates = utils.getWeekDates();
    const startDate = weekDates[0];
    const endDate = weekDates[6];
    
    const monthYear = startDate.toLocaleDateString('en-US', { 
      month: 'long', 
      year: 'numeric' 
    });
    
    let displayText = monthYear;
    if (startDate.getMonth() !== endDate.getMonth()) {
      const endMonth = endDate.toLocaleDateString('en-US', { month: 'short' });
      displayText = `${startDate.toLocaleDateString('en-US', { month: 'short' })} - ${endMonth} ${endDate.getFullYear()}`;
    }
    
    elements.calendarMonth.textContent = displayText;
    
    // Create header row
    const headerRow = document.createElement('div');
    headerRow.className = 'calendar-header-row';
    
    // Time header
    const timeHeader = document.createElement('div');
    timeHeader.className = 'calendar-time-header';
    timeHeader.textContent = 'Time';
    headerRow.appendChild(timeHeader);
    
    // Day headers
    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    days.forEach((day, dayIndex) => {
      const dayHeader = document.createElement('div');
      dayHeader.className = 'calendar-day-header';
      const dayDate = weekDates[dayIndex];
      
      // Check if this is today
      const isToday = dayDate.toDateString() === today.toDateString();
      if (isToday) {
        dayHeader.classList.add('today');
      }
      
      const dayName = document.createElement('div');
      dayName.className = 'calendar-day-name';
      dayName.textContent = day.slice(0, 3);
      
      const dateNum = document.createElement('div');
      dateNum.className = 'calendar-day-date';
      dateNum.textContent = dayDate.getDate();
      
      const weatherInfo = document.createElement('div');
      weatherInfo.className = 'calendar-day-weather';
      weatherInfo.dataset.day = day;
      
      const weatherIcon = document.createElement('i');
      weatherIcon.className = 'wi wi-day-sunny weather-icon';
      weatherIcon.style.display = 'none'; // Hide initially to prevent flash
      
      const weatherTemp = document.createElement('span');
      weatherTemp.className = 'weather-temp';
      weatherTemp.textContent = '--°';
      weatherTemp.style.display = 'none'; // Hide initially to prevent flash
      
      weatherInfo.appendChild(weatherIcon);
      weatherInfo.appendChild(weatherTemp);
      
      dayHeader.appendChild(dayName);
      dayHeader.appendChild(dateNum);
      dayHeader.appendChild(weatherInfo);
      headerRow.appendChild(dayHeader);
    });
    
    grid.appendChild(headerRow);
    
    // Create time slots and day columns (from 12 AM to 11 PM)
    for (let hour = 0; hour <= 23; hour++) {
      // Time slot
      const timeSlot = document.createElement('div');
      timeSlot.className = 'calendar-time-slot';
      timeSlot.style.gridColumn = '1';
      timeSlot.style.gridRow = hour + 2;
      
      const timeText = hour === 0 ? '12 AM' : 
                     hour < 12 ? `${hour} AM` : 
                     hour === 12 ? '12 PM' : 
                     `${hour - 12} PM`;
      timeSlot.textContent = timeText;
      grid.appendChild(timeSlot);
      
      // Day cells
      days.forEach((day, dayIndex) => {
        const cell = document.createElement('div');
        cell.className = 'calendar-hour-cell';
        cell.style.gridColumn = dayIndex + 2;
        cell.style.gridRow = hour + 2;
        cell.dataset.day = day;
        cell.dataset.hour = hour;

        const stack = document.createElement('div');
        stack.className = 'calendar-task-stack';
        cell.appendChild(stack);
        
        cell.addEventListener('click', (e) => {
          // Only handle if clicked on empty space (not on a task block)
          if (e.target.classList.contains('calendar-task-block')) {
            return; // Let the task block handle its own click
          }
          
          e.stopPropagation();
          console.log(`Calendar cell clicked: ${day} ${hour}:00`);
          
          state.editingTask = null;
          elements.taskForm.reset();
          
          document.getElementById('task-day').value = day;
          
          // Set default start time based on clicked hour, end time one hour later
          const startTime = `${hour.toString().padStart(2, '0')}:00`;
          const endHour = hour < 23 ? hour + 1 : 23;
          const endTime = `${endHour.toString().padStart(2, '0')}:00`;
          
          document.getElementById('task-start-time').value = startTime;
          document.getElementById('task-end-time').value = endTime;
          
          const modalHeader = elements.taskModal.querySelector('.modal-header h2');
          modalHeader.textContent = 'Create Task';
          
          const submitBtn = elements.taskForm.querySelector('button[type="submit"]');
          submitBtn.textContent = 'Create Task';
          
          ui.openModal(elements.taskModal);
        });
        
        grid.appendChild(cell);
      });
    }
    
    calendar.addCurrentTimeIndicator();
    calendar.renderTasks();
    
    // Update weather immediately after calendar renders (no delay)
    if (weather.lastWeatherData && weather.lastWeatherData.forecast) {
      weather.updateCalendarWeather(weather.lastWeatherData.forecast);
    }
  },

  addCurrentTimeIndicator() {
    const now = new Date();
    const currentHour = now.getHours();
    const currentMinutes = now.getMinutes();
    
    if (state.weekOffset === 0) {
      const currentDay = now.getDay(); // 0=Sunday, 1=Monday, etc.
      
      const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
      const dayName = days[currentDay];
      
      const cell = elements.calendarGrid.querySelector(
        `[data-day="${dayName}"][data-hour="${currentHour}"]`
      );
      
      if (cell) {
        const line = document.createElement('div');
        line.className = 'current-time-line';
        line.style.top = `${(currentMinutes / 60) * 100}%`;
        
        const dot = document.createElement('div');
        dot.className = 'current-time-dot';
        line.appendChild(dot);
        
        cell.appendChild(line);
      }
    }
  },

  renderTasks() {
    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    
    // Clear all existing task elements
    days.forEach(day => {
      for (let hour = 6; hour <= 23; hour++) {
        const cell = elements.calendarGrid.querySelector(`[data-day="${day}"][data-hour="${hour}"]`);
        if (cell) {
          const stack = cell.querySelector('.calendar-task-stack') || cell;
          stack.innerHTML = '';
        }
      }
    });
    
    days.forEach(day => {
      const weekKey = utils.getWeekKey(day);
      const dayTasks = state.tasks[weekKey] || [];
      
      // Filter and process tasks with time ranges
      const timeTasks = dayTasks.filter(task => !task.completed && (task.startTime || task.endTime || task.time));
      
      timeTasks.forEach(task => {
        this.renderTaskBlock(task, day);
      });
    });
  },
  
  renderTaskBlock(task, day) {
    let startTime, endTime;
    
    // Enhanced debugging for task time parsing
    console.log('🔍 Parsing task:', {
      title: task.title,
      time: task.time,
      startTime: task.startTime,
      endTime: task.endTime,
      hasTime: !!task.time,
      hasStartTime: !!task.startTime,
      hasEndTime: !!task.endTime,
      timeIncludesDash: task.time && task.time.includes('-')
    });
    
    // Parse time information - handle class tasks properly
    if (task.startTime && task.endTime) {
      // Most common case: separate start and end times
      startTime = task.startTime;
      endTime = task.endTime;
      console.log('📍 Using startTime/endTime:', { startTime, endTime });
    } else if (task.time && task.time.includes('-')) {
      // Legacy format: "HH:MM-HH:MM"
      [startTime, endTime] = task.time.split('-');
      console.log('📍 Using time range:', { startTime, endTime });
    } else if (task.time && task.endTime) {
      // Class task with start and end time
      startTime = task.time;
      endTime = task.endTime;
      console.log('📍 Using time + endTime:', { startTime, endTime });
    } else if (task.endTime && !task.time && !task.startTime) {
      // End time only - assume 1 hour duration, ending at the specified time
      endTime = task.endTime;
      const endHour = parseInt(endTime.split(':')[0]);
      const endMin = parseInt(endTime.split(':')[1] || 0);
      
      // Calculate start time as 1 hour before end time
      let startHour = endHour - 1;
      let startMin = endMin;
      
      // Handle hour wrapping (e.g., if end time is 00:30, start time should be 23:30)
      if (startHour < 0) {
        startHour = 23;
      }
      
      startTime = `${startHour.toString().padStart(2, '0')}:${startMin.toString().padStart(2, '0')}`;
    } else if (task.time) {
      // Single time - treat as 1 hour block
      startTime = task.time;
      const startHour = parseInt(startTime.split(':')[0]);
      const startMin = parseInt(startTime.split(':')[1] || 0);
      const endHour = startHour < 23 ? startHour + 1 : 0;
      endTime = `${endHour.toString().padStart(2, '0')}:${startMin.toString().padStart(2, '0')}`;
    } else {
      return; // No valid time information
    }

    // Convert times to minutes from midnight
    const startMinutes = this.timeToMinutes(startTime);
    const endMinutes = this.timeToMinutes(endTime);
    
    // Calculate duration carefully to avoid massive blocks
    let durationInMinutes;
    if (endMinutes >= startMinutes) {
      // Same day duration
      durationInMinutes = endMinutes - startMinutes;
    } else {
      // Cross-midnight duration - but cap it at 12 hours to prevent unreasonable blocks
      const crossMidnightDuration = (24 * 60) - startMinutes + endMinutes;
      if (crossMidnightDuration > 12 * 60) {
        // If calculated duration is more than 12 hours, assume it's an error and default to 1 hour
        console.warn('Unreasonable task duration detected, defaulting to 1 hour:', {
          task: task.title,
          startTime,
          endTime,
          calculatedDuration: crossMidnightDuration
        });
        durationInMinutes = 60; // 1 hour default
      } else {
        durationInMinutes = crossMidnightDuration;
      }
    }
    
    // Ensure minimum 5-minute duration for visibility, but don't artificially extend tasks
    durationInMinutes = Math.max(5, durationInMinutes);
    
    // Debug the time parsing
    console.log('🕐 TIME PARSING DEBUG:', {
      task: task.title,
      rawStartTime: startTime,
      rawEndTime: endTime,
      startMinutes: startMinutes,
      endMinutes: endMinutes,
      calculatedDuration: durationInMinutes,
      startTimeReadable: `${Math.floor(startMinutes/60)}:${String(startMinutes%60).padStart(2,'0')}`,
      endTimeReadable: `${Math.floor(endMinutes/60)}:${String(endMinutes%60).padStart(2,'0')}`,
      durationReadable: `${Math.floor(durationInMinutes/60)}h ${durationInMinutes%60}m`
    });
    
    // Use the actual calculated duration, not an artificial minimum
    // (startMinutes and endMinutes are already calculated above)
    
    // Find the appropriate hour cell to place the task
    const startHour = Math.floor(startMinutes / 60);
    console.log('🎯 Looking for cell:', `[data-day="${day}"][data-hour="${startHour}"]`);
    
    const cell = elements.calendarGrid.querySelector(`[data-day="${day}"][data-hour="${startHour}"]`);
    
    if (!cell) {
      console.log('❌ Cell not found for hour:', startHour, 'Available cells:', 
        elements.calendarGrid.querySelectorAll(`[data-day="${day}"]`).length);
      return;
    }
    
    console.log('✅ Found cell for hour:', startHour);    // Create task element
    const taskEl = document.createElement('div');
    taskEl.className = 'calendar-task-block';
    
    // Add duration-based styling
    if (durationInMinutes <= 30) {
      taskEl.setAttribute('data-duration', 'short');
    } else if (durationInMinutes <= 120) {
      taskEl.setAttribute('data-duration', 'medium');
    } else {
      taskEl.setAttribute('data-duration', 'long');
    }
    
    // Show time range in the task text
    const timeRange = `${utils.formatTime(startTime)} - ${utils.formatTime(endTime)}`;
    let timeDisplay = timeRange;
    
    // Add visual indicator if this is an end-time-only task with assumed start time
    if (task.endTime && !task.time && !task.startTime) {
      timeDisplay = `⏱️ ${timeRange}`;
      taskEl.title = `${task.title} (End time: ${utils.formatTime(task.endTime)} - Start time estimated)\n${task.description || ''}`;
    } else {
      taskEl.title = `${task.title} (${timeRange})${task.description ? '\n' + task.description : ''}`;
    }
    
    // Adjust content for very short tasks
    if (durationInMinutes <= 15) {
      taskEl.innerHTML = `<div style="font-weight: 600; font-size: 0.65rem;">${task.title}</div>`;
    } else {
      taskEl.innerHTML = `<div style="font-weight: 600; font-size: 0.75rem;">${task.title}</div>`;
    }

    // Apply styling
    if (task.color) {
      taskEl.style.backgroundColor = task.color;
      taskEl.style.borderLeft = `4px solid ${task.color}`;
      taskEl.style.color = 'white';
    } else {
      taskEl.style.backgroundColor = 'var(--primary)';
      taskEl.style.color = 'white';
    }    // Calculate position and size with minute-level precision
    // Use fixed 60px cell height for consistent calculations
    const cellHeight = 60;
    const minuteHeight = 1; // 1 pixel per minute (60px / 60 minutes)
    
    // Calculate start position with minute precision
    const startMinutesInHour = startMinutes % 60;
    const startOffset = startMinutesInHour; // Direct pixel offset
    
    // Calculate height with minute precision - use exact duration
    const heightInPixels = durationInMinutes; // Direct minute-to-pixel mapping
    
    // Debug logging with visual verification
    const expectedEndHour = Math.floor((startMinutes + durationInMinutes) / 60);
    const expectedEndMinute = (startMinutes + durationInMinutes) % 60;
    console.log('📐 SIMPLIFIED Calendar Debug:', {
      task: task.title,
      startTime,
      endTime,
      startMinutes: `${startMinutes} (${Math.floor(startMinutes/60)}:${String(startMinutes%60).padStart(2,'0')})`,
      endMinutes: `${endMinutes} (${Math.floor(endMinutes/60)}:${String(endMinutes%60).padStart(2,'0')})`,
      durationInMinutes,
      startOffset: startOffset,
      heightInPixels: heightInPixels,
      expectedEnd: `${expectedEndHour}:${String(expectedEndMinute).padStart(2,'0')}`,
      visualCheck: `Should start at ${Math.floor(startMinutes/60)} AM + ${startMinutes%60} minutes and be ${durationInMinutes} pixels tall`
    });

    taskEl.style.position = 'absolute';
    taskEl.style.top = `${startOffset}px`;
    taskEl.style.height = `${heightInPixels}px`;
    taskEl.style.left = '2px';
    taskEl.style.right = '2px';
    taskEl.style.zIndex = '10';
    taskEl.style.fontSize = '0.75rem';
    taskEl.style.padding = '2px 4px';
    taskEl.style.borderRadius = '4px';
    taskEl.style.overflow = 'hidden';
    taskEl.style.textOverflow = 'ellipsis';
    taskEl.style.whiteSpace = 'nowrap';
    taskEl.style.boxSizing = 'border-box'; // Ensure padding doesn't affect height    // Add click handler for editing
    taskEl.addEventListener('click', (e) => {
      e.stopPropagation();
      tasks.showEditForm(task);
    });
    
    // Ensure the cell has relative positioning
    if (!cell.style.position) {
      cell.style.position = 'relative';
    }
    
    cell.appendChild(taskEl);
  },
  
  timeToMinutes(timeStr) {
    // Handle both 12-hour and 24-hour formats
    let cleanTime = timeStr.toLowerCase().trim();
    let hours, minutes;
    
    if (cleanTime.includes('am') || cleanTime.includes('pm')) {
      // 12-hour format
      const isPM = cleanTime.includes('pm');
      cleanTime = cleanTime.replace(/[ap]m/g, '').trim();
      [hours, minutes] = cleanTime.split(':').map(Number);
      
      // Convert to 24-hour format
      if (isPM && hours !== 12) {
        hours += 12;
      } else if (!isPM && hours === 12) {
        hours = 0;
      }
    } else {
      // 24-hour format
      [hours, minutes] = cleanTime.split(':').map(Number);
    }
    
    return hours * 60 + (minutes || 0);
  }
};

// ===== Weather Component =====
const weather = {
  currentData: null,
  userLocation: null,
  lastWeatherData: null,
  
  async requestLocation() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error('Geolocation is not supported by this browser'));
        return;
      }
      
      navigator.geolocation.getCurrentPosition(
        (position) => {
          this.userLocation = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude
          };
          
          // Store permission status for future visits
          localStorage.setItem('weather_permission_granted', 'true');
          localStorage.setItem('weather_last_location', JSON.stringify(this.userLocation));
          this.markWeatherInteractionComplete();
          
          resolve(this.userLocation);
        },
        (error) => {
          let message = 'Location access denied';
          switch(error.code) {
            case error.PERMISSION_DENIED:
              message = 'Location access denied by user';
              localStorage.setItem('weather_permission_granted', 'false');
              break;
            case error.POSITION_UNAVAILABLE:
              message = 'Location information unavailable';
              break;
            case error.TIMEOUT:
              message = 'Location request timed out';
              break;
          }
          reject(new Error(message));
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 300000 // 5 minutes
        }
      );
    });
  },
  
  checkStoredPermission() {
    const permissionGranted = localStorage.getItem('weather_permission_granted');
    const lastLocation = localStorage.getItem('weather_last_location');
    
    console.log('Checking stored permission:', permissionGranted, 'Location:', lastLocation);
    
    if (permissionGranted === 'true' && lastLocation) {
      try {
        this.userLocation = JSON.parse(lastLocation);
        console.log('Using stored location:', this.userLocation);
        return true;
      } catch (e) {
        console.log('Error parsing stored location:', e);
        localStorage.removeItem('weather_last_location');
        return false;
      }
    }
    return false;
  },
  
  hasInteractedWithWeather() {
    return localStorage.getItem('weather_interaction_completed') === 'true';
  },
  
  markWeatherInteractionComplete() {
    localStorage.setItem('weather_interaction_completed', 'true');
  },
  
  shouldRefreshWeather() {
    const lastUpdateDate = localStorage.getItem('weather_last_update_date');
    const today = new Date().toDateString();
    
    // Refresh if it's a new day or no previous update
    return !lastUpdateDate || lastUpdateDate !== today;
  },
  
  markWeatherUpdated() {
    const today = new Date().toDateString();
    localStorage.setItem('weather_last_update_date', today);
  },
  
  async requestLocationAndLoadWeather() {
    console.log('🌍 Requesting location permission automatically...');
    
    // Show loading state on weather button
    if (elements.weatherBtn) {
      elements.weatherBtn.innerHTML = `
        <div class="loading-spinner"></div>
        <span>Loading...</span>
      `;
      elements.weatherBtn.classList.add('loading');
      elements.weatherBtn.title = 'Loading weather data...';
    }
    
    if ('geolocation' in navigator) {
      try {
        console.log('📍 Getting current position...');
        const position = await new Promise((resolve, reject) => {
          navigator.geolocation.getCurrentPosition(resolve, reject, {
            timeout: 10000,
            enableHighAccuracy: true
          });
        });
        
        this.userLocation = {
          lat: position.coords.latitude,
          lon: position.coords.longitude
        };
        
        console.log('✅ Got location:', this.userLocation);
        
        // Store permission and location
        localStorage.setItem('weather_permission_granted', 'true');
        localStorage.setItem('weather_last_location', JSON.stringify(this.userLocation));
        this.markWeatherInteractionComplete();
        
        console.log('🌤️ Loading weather data...');
        // Load weather data
        await this.loadWeatherDataSilently();
        
        // Update button for current day
        if (this.lastWeatherData) {
          this.updateButtonForSelectedDay(state.currentDay);
        }
        
        console.log('🎉 Weather loaded automatically on first visit');
      } catch (error) {
        console.log('❌ Location permission denied or failed:', error);
        // Reset button to default state
        if (elements.weatherBtn) {
          elements.weatherBtn.classList.remove('loading');
          elements.weatherBtn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path>
            </svg>
          `;
          elements.weatherBtn.classList.add('icon-only');
          elements.weatherBtn.title = 'Check Weather';
        }
      }
    }
  },
  
  async getWeatherByCoordinates(lat, lon) {
    try {
      const response = await fetch('/api/weather', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          latitude: lat,
          longitude: lon
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to fetch weather');
      }
      
      const data = await response.json();
      console.log('🌤️ Weather API response:', data);
      console.log('🌤️ Current weather:', data.current);
      console.log('🌤️ Forecast data:', data.forecast);
      
      this.currentData = data;
      this.updateButtonDisplay(data.current);
      return data;
    } catch (error) {
      console.error('Weather fetch error:', error);
      throw error;
    }
  },
  
  async getWeatherForCity(city) {
    try {
      const response = await fetch(`/api/weather/city/${encodeURIComponent(city)}`);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to fetch weather');
      }
      
      const data = await response.json();
      return data;
    } catch (error) {
      console.error('City weather fetch error:', error);
      throw error;
    }
  },
  
  updateButtonDisplay(currentWeather) {
    if (currentWeather && elements.weatherTemp) {
      elements.weatherTemp.textContent = `${currentWeather.temperature}°`;
      
      // Update weather icon
      const weatherIcon = document.getElementById('weather-icon');
      if (weatherIcon) {
        weatherIcon.className = `wi ${currentWeather.icon_class}`;
      }
      
      // Update button styling to show it has temperature
      if (elements.weatherBtn) {
        elements.weatherBtn.classList.remove('icon-only');
      }
      
      elements.weatherBtn.title = `${currentWeather.condition} in ${currentWeather.location} - ${currentWeather.temperature}°F`;
    }
  },
  
  updateButtonDisplayForDay(weatherData, isToday) {
    if (!weatherData) return;
    
    // Update weather icon
    const weatherIcon = document.getElementById('weather-icon');
    if (weatherIcon) {
      weatherIcon.className = `wi ${weatherData.icon_class}`;
    }
    
    // Update temperature (only show for today)
    const hasTemperature = isToday && weatherData.temperature !== null;
    if (elements.weatherTemp) {
      if (hasTemperature) {
        elements.weatherTemp.textContent = `${weatherData.temperature}°`;
      } else {
        elements.weatherTemp.textContent = '';
      }
    }
    
    // Adjust button styling based on temperature presence
    if (elements.weatherBtn) {
      if (hasTemperature) {
        elements.weatherBtn.classList.remove('icon-only');
        elements.weatherBtn.title = `${weatherData.condition} in ${weatherData.location} - ${weatherData.temperature}°F`;
      } else {
        elements.weatherBtn.classList.add('icon-only');
        elements.weatherBtn.title = `${weatherData.condition} - Click to check weather`;
      }
    }
  },
  
  updateButtonForSelectedDay(selectedDay) {
    if (!this.lastWeatherData) {
      this.showDefaultWeatherButton();
      return;
    }
    
    // Calculate the actual date for the selected day
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    const selectedDate = new Date(today);
    const dayIndex = this.getDayIndex(selectedDay);
    const todayIndex = today.getDay();
    
    // Calculate days difference accounting for week navigation
    let daysDifference = dayIndex - todayIndex + (state.weekOffset * 7);
    selectedDate.setDate(today.getDate() + daysDifference);
    
    // Find the appropriate weather data
    let weatherData = null;
    
    if (daysDifference === 0) {
      // Today - use current weather with temperature
      weatherData = this.lastWeatherData.current;
    } else {
      // Other days - show generic weather icon only, no temperature
      weatherData = {
        temperature: null, // No temperature for non-current days
        icon_class: 'wi-day-cloudy', // Generic weather icon
        condition: 'Weather',
        location: this.lastWeatherData.current ? this.lastWeatherData.current.location : 'Unknown'
      };
    }
    
    if (weatherData) {
      this.updateButtonDisplayForDay(weatherData, daysDifference === 0);
    } else {
      // No weather data available - show default
      this.showDefaultWeatherButton();
    }
  },
  
  showDefaultWeatherButton() {
    if (elements.weatherTemp) {
      elements.weatherTemp.textContent = '';
    }
    
    const weatherIcon = document.getElementById('weather-icon');
    if (weatherIcon) {
      weatherIcon.className = 'wi wi-day-cloudy';
    }
    
    if (elements.weatherBtn) {
      elements.weatherBtn.classList.add('icon-only');
      elements.weatherBtn.title = 'Check Weather';
    }
  },
  
  getDayIndex(dayName) {
    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    return days.indexOf(dayName);
  },
  
  showModal() {
    const modal = elements.weatherModal;
    const locationEl = document.getElementById('location-request');
    const loadingEl = document.getElementById('weather-loading');
    const dataEl = document.getElementById('weather-data');
    const errorEl = document.getElementById('weather-error');
    
    // Check if we already have weather data loaded
    if (this.lastWeatherData && this.userLocation) {
      // Show weather data directly
      locationEl.style.display = 'none';
      loadingEl.style.display = 'none';
      dataEl.style.display = 'block';
      errorEl.style.display = 'none';
    } else if (this.userLocation) {
      // Have location but no data, load it
      locationEl.style.display = 'none';
      loadingEl.style.display = 'block';
      dataEl.style.display = 'none';
      errorEl.style.display = 'none';
      this.loadWeatherData();
    } else {
      // First time, show location request
      locationEl.style.display = 'block';
      loadingEl.style.display = 'none';
      dataEl.style.display = 'none';
      errorEl.style.display = 'none';
    }
    
    ui.openModal(modal);
  },
  
  async loadWeatherData() {
    if (!this.userLocation) return;
    
    const locationEl = document.getElementById('location-request');
    const loadingEl = document.getElementById('weather-loading');
    const dataEl = document.getElementById('weather-data');
    const errorEl = document.getElementById('weather-error');
    
    // Show loading state
    locationEl.style.display = 'none';
    loadingEl.style.display = 'block';
    dataEl.style.display = 'none';
    errorEl.style.display = 'none';
    
    // Update loading text
    const loadingText = loadingEl.querySelector('p');
    if (loadingText) {
      loadingText.textContent = 'Loading weather data...';
    }
    
    try {
      console.log('🌤️ Fetching weather data for coordinates:', this.userLocation);
      
      const weatherData = await this.getWeatherByCoordinates(
        this.userLocation.latitude, 
        this.userLocation.longitude
      );
      
      if (!weatherData) {
        throw new Error('No weather data received');
      }
      
      this.lastWeatherData = weatherData;
      console.log('✅ Weather data loaded successfully:', weatherData);
      
      // Update sidebar weather if available
      if (weatherData.current) {
        this.updateSidebarWeather(weatherData.forecast || []);
      }
      
      // Update modal display to show weather data
      locationEl.style.display = 'none';
      loadingEl.style.display = 'none';
      dataEl.style.display = 'block';
      errorEl.style.display = 'none';
      
      // Update weather data in modal
      this.displayWeatherData(weatherData);
      
      // Update button for currently selected day
      this.updateButtonForSelectedDay(state.currentDay);
      
      // Show success notification
      ui.showNotification('Weather data loaded successfully! 🌤️', 'success');
      
    } catch (error) {
      console.error('❌ Weather loading error:', error);
      
      // Show error state
      locationEl.style.display = 'none';
      loadingEl.style.display = 'none';
      dataEl.style.display = 'none';
      errorEl.style.display = 'block';
      
      this.showError(error.message || 'Failed to load weather data');
    }
  },
  
  async loadWeatherDataSilently() {
    if (!this.userLocation) return;
    
    try {
      const data = await this.getWeatherByCoordinates(
        this.userLocation.lat || this.userLocation.latitude, 
        this.userLocation.lon || this.userLocation.longitude
      );
      
      this.displayWeatherData(data);
      
      // Prepare modal to show weather data directly
      const locationEl = document.getElementById('location-request');
      const loadingEl = document.getElementById('weather-loading');
      const dataEl = document.getElementById('weather-data');
      const errorEl = document.getElementById('weather-error');
      
      locationEl.style.display = 'none';
      loadingEl.style.display = 'none';
      dataEl.style.display = 'block';
      errorEl.style.display = 'none';
      
    } catch (error) {
      console.error('Silent weather loading failed:', error);
      // Don't show error in UI for silent loading
    }
  },
  
  displayWeatherData(data) {
    const { current, forecast } = data;
    
    // Store weather data for later use
    this.lastWeatherData = data;
    
    // Cache weather data in localStorage for refresh persistence
    try {
      localStorage.setItem('weather_last_data', JSON.stringify(data));
      console.log('Weather data cached successfully');
    } catch (e) {
      console.error('Failed to cache weather data:', e);
    }
    
    // Update current weather in modal
    document.getElementById('current-weather-icon').className = `wi ${current.icon_class}`;
    document.getElementById('current-temp').textContent = `${current.temperature}°F`;
    document.getElementById('current-condition').textContent = current.condition;
    document.getElementById('current-location').textContent = `📍 ${current.location}`;
    
    // Update current details
    document.getElementById('feels-like').textContent = `${current.feels_like}°F`;
    document.getElementById('humidity').textContent = `${current.humidity}%`;
    document.getElementById('wind-speed').textContent = `${current.wind_speed} mph`;
    
    // Update 6-day forecast in modal (today + next 5 days)
    const forecastGrid = document.getElementById('forecast-grid');
    forecastGrid.innerHTML = '';
    
    // Get next 6 days starting from today
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    
    const next6Days = [];
    for (let i = 0; i < 6; i++) {
      const futureDate = new Date(today);
      futureDate.setDate(today.getDate() + i);
      next6Days.push(dayNames[futureDate.getDay()]);
    }
    
    // Only show forecast for the next 6 days
    next6Days.forEach(dayName => {
      const day = forecast.find(d => d.day === dayName);
      if (day) {
        const forecastItem = document.createElement('div');
        forecastItem.className = 'forecast-item';
        
        forecastItem.innerHTML = `
          <div class="forecast-day">${day.day.substring(0, 3)}</div>
          <div class="forecast-icon">
            <i class="wi ${day.icon_class}"></i>
          </div>
          <div class="forecast-temps">
            <div class="forecast-high">${day.high_temp}°</div>
            <div class="forecast-low">${day.low_temp}°</div>
          </div>
        `;
        
        forecastGrid.appendChild(forecastItem);
      }
    });
    
    // Update sidebar day weather
    this.updateSidebarWeather(forecast);
    
    // Update calendar day weather
    this.updateCalendarWeather(forecast);
    
    // Update weather button display
    this.updateButtonDisplay(current);
    
    // Mark weather as updated for today
    this.markWeatherUpdated();
  },
  
  updateSidebarWeather(forecast) {
    const today = new Date();
    today.setHours(0, 0, 0, 0); // Reset time for accurate date comparison
    const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    
    // Clear all weather first
    const allDayElements = document.querySelectorAll('.day-weather');
    allDayElements.forEach(el => {
      const iconEl = el.querySelector('.weather-icon');
      const tempEl = el.querySelector('.weather-temp');
      if (iconEl) iconEl.style.display = 'none';
      if (tempEl) tempEl.style.display = 'none';
    });
    
    // Get the next 6 days starting from today
    const next6Days = [];
    for (let i = 0; i < 6; i++) {
      const futureDate = new Date(today);
      futureDate.setDate(today.getDate() + i);
      next6Days.push({
        date: futureDate,
        dayName: dayNames[futureDate.getDay()]
      });
    }
    
    // Get current week dates to check what's visible in sidebar
    const currentWeekDates = utils.getWeekDates();
    
    // Only show weather for the next 6 days that are also visible in the current sidebar week
    next6Days.forEach(({ date, dayName }, index) => {
      // Check if this future date is in the currently displayed week in sidebar
      const isInCurrentWeek = currentWeekDates.some(weekDate => {
        const checkDate = new Date(weekDate);
        checkDate.setHours(0, 0, 0, 0);
        return checkDate.getTime() === date.getTime();
      });
      
      if (isInCurrentWeek) {
        const dayWeatherEl = document.querySelector(`.day-weather[data-day="${dayName}"]`);
        
        if (dayWeatherEl) {
          const iconEl = dayWeatherEl.querySelector('.weather-icon');
          const tempEl = dayWeatherEl.querySelector('.weather-temp');
          
          if (index === 0) {
            // Today - use current weather data
            if (this.lastWeatherData && this.lastWeatherData.current) {
              const currentData = this.lastWeatherData.current;
              if (iconEl) {
                iconEl.className = `wi ${currentData.icon_class} weather-icon`;
                iconEl.style.display = 'block';
              }
              if (tempEl) {
                tempEl.textContent = `${currentData.temperature}°`;
                tempEl.style.display = 'block';
              }
            }
          } else {
            // Future days - use forecast data
            const dayData = forecast.find(day => day.day === dayName);
            if (dayData) {
              if (iconEl) {
                iconEl.className = `wi ${dayData.icon_class} weather-icon`;
                iconEl.style.display = 'block';
              }
              if (tempEl) {
                tempEl.textContent = `${dayData.high_temp}°`;
                tempEl.style.display = 'block';
              }
            }
          }
        }
      }
    });
  },
  
  updateCalendarWeather(forecast) {
    const today = new Date();
    today.setHours(0, 0, 0, 0); // Reset time for accurate date comparison
    const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    const todayName = dayNames[today.getDay()];
    
    // Clear all weather first
    const allCalendarWeatherElements = document.querySelectorAll('.calendar-day-weather');
    allCalendarWeatherElements.forEach(el => {
      const iconEl = el.querySelector('.weather-icon');
      const tempEl = el.querySelector('.weather-temp');
      if (iconEl) iconEl.style.display = 'none';
      if (tempEl) tempEl.style.display = 'none';
    });
    
    // Get the next 6 days starting from today
    const next6Days = [];
    for (let i = 0; i < 6; i++) {
      const futureDate = new Date(today);
      futureDate.setDate(today.getDate() + i);
      next6Days.push({
        date: futureDate,
        dayName: dayNames[futureDate.getDay()]
      });
    }
    
    // Get current week dates to check if they're in the visible week
    const currentWeekDates = utils.getWeekDates();
    
    // Only show weather for the next 6 days that are also visible in the current calendar week
    next6Days.forEach(({ date, dayName }, index) => {
      // Check if this future date is in the currently displayed week
      const isInCurrentWeek = currentWeekDates.some(weekDate => {
        weekDate.setHours(0, 0, 0, 0);
        return weekDate.getTime() === date.getTime();
      });
      
      if (isInCurrentWeek) {
        const calendarWeatherEl = document.querySelector(`.calendar-day-weather[data-day="${dayName}"]`);
        
        if (calendarWeatherEl) {
          const iconEl = calendarWeatherEl.querySelector('.weather-icon');
          const tempEl = calendarWeatherEl.querySelector('.weather-temp');
          
          if (index === 0) {
            // Today - use current weather data
            if (this.lastWeatherData && this.lastWeatherData.current) {
              const currentData = this.lastWeatherData.current;
              
              if (iconEl) {
                iconEl.className = `wi ${currentData.icon_class} weather-icon`;
                iconEl.style.display = 'block';
                iconEl.classList.add('today-weather');
              }
              
              if (tempEl) {
                tempEl.textContent = `${currentData.temperature}°`;
                tempEl.style.display = 'block';
                tempEl.classList.add('today-weather');
              }
            }
          } else {
            // Future days - use forecast data
            const dayData = forecast.find(day => day.day === dayName);
            if (dayData) {
              if (iconEl) {
                iconEl.className = `wi ${dayData.icon_class} weather-icon`;
                iconEl.style.display = 'block';
                iconEl.classList.remove('today-weather');
              }
              
              if (tempEl) {
                tempEl.textContent = `${dayData.high_temp}°`;
                tempEl.style.display = 'block';
                tempEl.classList.remove('today-weather');
              }
            }
          }
        }
      }
    });
  },
  
  showError(message) {
    document.getElementById('weather-error-message').textContent = message;
  },
  
  async refreshWeather() {
    if (!this.userLocation) {
      this.showError('Location not available. Please allow location access.');
      return;
    }
    
    await this.loadWeatherData();
  },
  
  async searchCity(city) {
    if (!city.trim()) return;
    
    const loadingEl = document.getElementById('weather-loading');
    const dataEl = document.getElementById('weather-data');
    const errorEl = document.getElementById('weather-error');
    
    loadingEl.style.display = 'block';
    dataEl.style.display = 'none';
    errorEl.style.display = 'none';
    
    try {
      const data = await this.getWeatherForCity(city);
      loadingEl.style.display = 'none';
      this.displayWeatherData(data);
      this.markWeatherInteractionComplete(); // Mark interaction complete for manual city search
      dataEl.style.display = 'block';
    } catch (error) {
      loadingEl.style.display = 'none';
      this.showError(error.message);
      errorEl.style.display = 'block';
    }
  },
  
  async searchCityWithCoordinates(city, latitude, longitude) {
    if (!latitude || !longitude) return;
    
    const loadingEl = document.getElementById('weather-loading');
    const dataEl = document.getElementById('weather-data');
    const errorEl = document.getElementById('weather-error');
    
    loadingEl.style.display = 'block';
    dataEl.style.display = 'none';
    errorEl.style.display = 'none';
    
    try {
      const response = await fetch('/api/weather/coordinates', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          latitude: latitude,
          longitude: longitude
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to fetch weather');
      }
      
      const data = await response.json();
      loadingEl.style.display = 'none';
      this.displayWeatherData(data);
      this.markWeatherInteractionComplete();
      dataEl.style.display = 'block';
    } catch (error) {
      loadingEl.style.display = 'none';
      this.showError(error.message);
      errorEl.style.display = 'block';
    }
  },
  
  async searchCities(query) {
    if (!query || query.length < 2) return [];
    
    try {
      const response = await fetch(`/api/cities/search?q=${encodeURIComponent(query)}&limit=10`);
      if (!response.ok) {
        throw new Error('Failed to search cities');
      }
      
      const data = await response.json();
      return data.results || [];
    } catch (error) {
      console.error('City search error:', error);
      return [];
    }
  },
  
  setupAutocomplete(inputId, dropdownId) {
    const input = document.getElementById(inputId);
    const dropdown = document.getElementById(dropdownId);
    
    if (!input || !dropdown) return;
    
    let currentSelection = -1;
    let searchTimeout = null;
    
    // Search on input
    input.addEventListener('input', async (e) => {
      const query = e.target.value.trim();
      
      if (searchTimeout) {
        clearTimeout(searchTimeout);
      }
      
      if (query.length < 2) {
        dropdown.style.display = 'none';
        return;
      }
      
      // Debounce search
      searchTimeout = setTimeout(async () => {
        dropdown.innerHTML = '<div class="autocomplete-loading">Searching cities...</div>';
        dropdown.style.display = 'block';
        
        const cities = await this.searchCities(query);
        
        if (cities.length === 0) {
          dropdown.innerHTML = '<div class="autocomplete-no-results">No cities found</div>';
        } else {
          dropdown.innerHTML = cities.map((city, index) => `
            <div class="autocomplete-item" data-index="${index}" data-city="${city.display_name}" data-lat="${city.latitude}" data-lng="${city.longitude}">
              <div class="autocomplete-item-main">
                <div class="autocomplete-city">${city.city}</div>
                <div class="autocomplete-state">${city.state}</div>
              </div>
              <div class="autocomplete-population">${city.population > 0 ? city.population.toLocaleString() : ''}</div>
            </div>
          `).join('');
          
          // Add click handlers
          dropdown.querySelectorAll('.autocomplete-item').forEach(item => {
            item.addEventListener('click', (e) => {
              const city = item.dataset.city;
              const lat = parseFloat(item.dataset.lat);
              const lng = parseFloat(item.dataset.lng);
              
              input.value = city;
              dropdown.style.display = 'none';
              currentSelection = -1;
              
              // Use coordinates for more accurate weather
              this.searchCityWithCoordinates(city, lat, lng);
            });
          });
        }
      }, 300);
    });
    
    // Keyboard navigation
    input.addEventListener('keydown', (e) => {
      const items = dropdown.querySelectorAll('.autocomplete-item');
      
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        currentSelection = Math.min(currentSelection + 1, items.length - 1);
        this.updateSelection(items, currentSelection);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        currentSelection = Math.max(currentSelection - 1, -1);
        this.updateSelection(items, currentSelection);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (currentSelection >= 0 && items[currentSelection]) {
          items[currentSelection].click();
        } else {
          // Fallback to regular city search
          this.searchCity(input.value);
          dropdown.style.display = 'none';
        }
      } else if (e.key === 'Escape') {
        dropdown.style.display = 'none';
        currentSelection = -1;
      }
    });
    
    // Hide dropdown when clicking outside
    document.addEventListener('click', (e) => {
      if (!input.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.style.display = 'none';
        currentSelection = -1;
      }
    });
  },
  
  updateSelection(items, index) {
    items.forEach((item, i) => {
      if (i === index) {
        item.classList.add('highlighted');
      } else {
        item.classList.remove('highlighted');
      }
    });
  },
  
  // Auto-update weather button every 30 minutes
  startAutoUpdate() {
    if (this.userLocation) {
      setInterval(() => {
        this.getWeatherByCoordinates(
          this.userLocation.latitude, 
          this.userLocation.longitude
        ).catch(console.error);
      }, 30 * 60 * 1000); // 30 minutes
    }
  }
};

// ===== Notification Scheduler =====
const notificationScheduler = {
  permission: null,
  scheduledNotifications: new Map(), // Track scheduled notifications
  dailySummaryTimer: null,
  
  async init() {
    // Request notification permission
    if ('Notification' in window) {
      this.permission = await Notification.requestPermission();
      console.log('📢 Notification permission:', this.permission);
    }
    
    // Schedule daily summary for end of day (11:30 PM)
    this.scheduleDailySummary();
    
    // Check for task reminders every minute
    this.startReminderChecker();
    
    // Schedule existing tasks
    this.scheduleAllTaskReminders();
  },
  
  async sendNotification(title, body, options = {}) {
    if (this.permission !== 'granted') {
      console.warn('📢 Notification permission not granted');
      return;
    }
    
    try {
      const notification = new Notification(title, {
        body,
        icon: '/static/PlannerIcon.png',
        badge: '/static/PlannerIcon.png',
        tag: options.tag || 'planner-notification',
        requireInteraction: options.requireInteraction || false,
        silent: options.silent || false,
        ...options
      });
      
      // Auto-close after 10 seconds unless it requires interaction
      if (!options.requireInteraction) {
        setTimeout(() => notification.close(), 10000);
      }
      
      return notification;
    } catch (error) {
      console.error('📢 Failed to send notification:', error);
    }
  },
  
  scheduleTaskReminders(task) {
    if (!task.startTime && !task.endTime) return;
    
    // Use endTime if available, otherwise startTime
    const taskTime = task.endTime || task.startTime;
    if (!taskTime) return;
    
    const taskDateTime = this.getTaskDateTime(task, taskTime);
    if (!taskDateTime || taskDateTime <= new Date()) return;
    
    const taskId = task.id;
    
    // Clear existing reminders for this task
    this.clearTaskReminders(taskId);
    
    // Use custom reminder times from user settings
    const customTimes = state.userSettings.custom_reminder_times || [300, 60, 30];
    
    customTimes.forEach((minutes) => {
      const reminderTime = new Date(taskDateTime.getTime() - (minutes * 60 * 1000));
      
      if (reminderTime > new Date()) {
        const timeoutId = setTimeout(() => {
          this.sendTaskReminder(task, this.formatReminderTime(minutes));
        }, reminderTime.getTime() - Date.now());
        
        // Store the timeout ID for later cancellation
        const reminderKey = `${taskId}-${minutes}`;
        this.scheduledNotifications.set(reminderKey, timeoutId);
        
        console.log(`📅 Scheduled reminder for "${task.title}" - ${this.formatReminderTime(minutes)} before (${reminderTime.toLocaleString()})`);
      }
    });
  },
  
  clearTaskReminders(taskId) {
    // Clear all reminders for a specific task
    const keysToRemove = [];
    for (const [key, timeoutId] of this.scheduledNotifications) {
      if (key.startsWith(taskId + '-')) {
        clearTimeout(timeoutId);
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach(key => this.scheduledNotifications.delete(key));
  },
  
  scheduleAllTaskReminders() {
    // Schedule reminders for all existing tasks
    Object.values(state.tasks).forEach(dayTasks => {
      dayTasks.forEach(task => {
        if (!task.completed) {
          this.scheduleTaskReminders(task);
        }
      });
    });
  },
  
  getTaskDateTime(task, time) {
    // Get the full date and time for a task
    const today = new Date();
    const dayIndex = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'].indexOf(task.day);
    const currentDayIndex = today.getDay();
    
    // Calculate days until task day
    let daysUntil = dayIndex - currentDayIndex;
    if (daysUntil < 0) daysUntil += 7; // Next week
    
    const taskDate = new Date(today);
    taskDate.setDate(today.getDate() + daysUntil);
    
    // Parse time (format: "HH:MM" or "H:MM AM/PM")
    const [hours, minutes] = this.parseTime(time);
    taskDate.setHours(hours, minutes, 0, 0);
    
    return taskDate;
  },
  
  parseTime(timeStr) {
    // Parse time string to hours and minutes
    let cleanTime = timeStr.toLowerCase().trim();
    let hours, minutes;
    
    if (cleanTime.includes('am') || cleanTime.includes('pm')) {
      // 12-hour format
      const isPM = cleanTime.includes('pm');
      cleanTime = cleanTime.replace(/[ap]m/g, '').trim();
      [hours, minutes] = cleanTime.split(':').map(Number);
      
      // Convert to 24-hour format
      if (isPM && hours !== 12) {
        hours += 12;
      } else if (!isPM && hours === 12) {
        hours = 0;
      }
    } else {
      // 24-hour format
      [hours, minutes] = cleanTime.split(':').map(Number);
    }
    
    return [hours, minutes || 0];
  },
  
  async sendTaskReminder(task, timeLabel) {
    const taskTime = task.endTime || task.startTime;
    const timeDisplay = utils.formatTime(taskTime);
    
    await this.sendNotification(
      `📅 Task Reminder - ${timeLabel}`,
      `"${task.title}" is due at ${timeDisplay} on ${task.day}`,
      {
        tag: `task-reminder-${task.id}`,
        requireInteraction: true,
        actions: [
          { action: 'view', title: 'View Task' },
          { action: 'dismiss', title: 'Dismiss' }
        ]
      }
    );
  },
  
  formatReminderTime(minutes) {
    if (minutes < 60) {
      return `${minutes} minutes`;
    } else if (minutes < 1440) { // Less than 24 hours
      const hours = Math.floor(minutes / 60);
      const remainingMinutes = minutes % 60;
      if (remainingMinutes === 0) {
        return hours === 1 ? '1 hour' : `${hours} hours`;
      } else {
        return `${hours}h ${remainingMinutes}m`;
      }
    } else { // 24 hours or more
      const days = Math.floor(minutes / 1440);
      const remainingHours = Math.floor((minutes % 1440) / 60);
      if (remainingHours === 0) {
        return days === 1 ? '1 day' : `${days} days`;
      } else {
        return `${days}d ${remainingHours}h`;
      }
    }
  },

  scheduleDailySummary() {
    // Use custom daily summary time from user settings
    const summaryTimeStr = state.userSettings.daily_summary_time || '23:30';
    const [summaryHour, summaryMinute] = summaryTimeStr.split(':').map(Number);
    
    // Schedule daily summary for the specified time every day
    const now = new Date();
    const summaryTime = new Date();
    summaryTime.setHours(summaryHour, summaryMinute, 0, 0);
    
    // If it's already past the summary time today, schedule for tomorrow
    if (summaryTime <= now) {
      summaryTime.setDate(summaryTime.getDate() + 1);
    }
    
    const timeUntilSummary = summaryTime.getTime() - now.getTime();
    
    this.dailySummaryTimer = setTimeout(() => {
      this.sendDailySummary();
      // Schedule next day's summary
      this.scheduleDailySummary();
    }, timeUntilSummary);
    
    console.log(`📊 Daily summary scheduled for ${summaryTime.toLocaleString()}`);
  },
  
  async sendDailySummary() {
    const today = new Date();
    const dayName = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][today.getDay()];
    const weekKey = utils.getWeekKey(dayName);
    const todayTasks = state.tasks[weekKey] || [];
    
    const completedTasks = todayTasks.filter(task => task.completed);
    const pendingTasks = todayTasks.filter(task => !task.completed);
    
    let summaryBody = `📋 Today's Summary (${dayName}):\n`;
    summaryBody += `✅ Completed: ${completedTasks.length} tasks\n`;
    summaryBody += `⏳ Pending: ${pendingTasks.length} tasks\n`;
    
    if (pendingTasks.length > 0) {
      summaryBody += `\nPending tasks:\n`;
      pendingTasks.slice(0, 3).forEach(task => {
        const timeInfo = task.startTime || task.endTime ? ` (${utils.formatTime(task.startTime || task.endTime)})` : '';
        summaryBody += `• ${task.title}${timeInfo}\n`;
      });
      if (pendingTasks.length > 3) {
        summaryBody += `• ... and ${pendingTasks.length - 3} more`;
      }
    }
    
    await this.sendNotification(
      '🌙 Daily Planner Summary',
      summaryBody,
      {
        tag: 'daily-summary',
        requireInteraction: true
      }
    );
  },
  
  startReminderChecker() {
    // Check every minute for any reminders that need to be sent
    setInterval(() => {
      this.scheduleAllTaskReminders();
    }, 60000); // Check every minute
  },
  
  // Public methods for task lifecycle integration
  onTaskCreated(task) {
    this.scheduleTaskReminders(task);
  },
  
  onTaskUpdated(task) {
    this.clearTaskReminders(task.id);
    if (!task.completed) {
      this.scheduleTaskReminders(task);
    }
  },
  
  onTaskDeleted(taskId) {
    this.clearTaskReminders(taskId);
  },
  
  onTaskCompleted(taskId) {
    this.clearTaskReminders(taskId);
  }
};

// ===== Assistant =====
const assistant = {
  isOpen: false,
  isRecording: false,
  recognition: null,
  conversationHistory: [], // Add conversation history for context
  isProcessing: false, // Prevent duplicate requests
  
  init() {
    // Initialize speech recognition if supported
    console.log('🎤 Checking speech recognition support...');
    console.log('🎤 webkitSpeechRecognition:', 'webkitSpeechRecognition' in window);
    console.log('🎤 SpeechRecognition:', 'SpeechRecognition' in window);
    
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      try {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        console.log('🎤 Creating SpeechRecognition instance...');
        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false;
        this.recognition.interimResults = false;
        this.recognition.lang = 'en-US';
        console.log('🎤 Speech recognition initialized successfully');
      } catch (error) {
        console.error('🎤 Failed to initialize speech recognition:', error);
        this.recognition = null;
      }
      
      // Only set up event handlers if recognition was created successfully
      if (this.recognition) {
        this.recognition.onstart = () => {
        console.log('🎤 Recognition started successfully');
        this.isRecording = true;
        this.updateVoiceButtonState(true);
        ui.showNotification('Listening... Speak now!', 'info');
      };
      
      this.recognition.onend = () => {
        console.log('🎤 Recognition ended');
        this.isRecording = false;
        this.updateVoiceButtonState(false);
      };
      
      this.recognition.onresult = (event) => {
        console.log('🎤 Recognition result received:', event);
        console.log('🎤 Results length:', event.results?.length);
        
        if (event.results && event.results.length > 0) {
          const result = event.results[0];
          console.log('🎤 Result confidence:', result.confidence);
          console.log('🎤 Result alternatives:', result.length);
          
          if (result[0] && result[0].transcript) {
            const transcript = result[0].transcript.trim();
            console.log('🎤 Raw transcript:', transcript);
            
            if (transcript) {
              elements.assistantInput.value = transcript;
              console.log('🎤 Voice input received:', transcript);
              ui.showNotification('Voice input received!', 'success');
              
              // Auto-send after voice input with a longer delay
              setTimeout(() => {
                if (!this.isProcessing) {
                  console.log('🎤 Auto-sending voice message');
                  this.sendMessage();
                } else {
                  console.log('⚠️ Voice auto-send skipped, already processing');
                  ui.showNotification('Voice message ready to send', 'info');
                }
              }, 800);
            } else {
              console.log('⚠️ Empty transcript after trim');
              ui.showNotification('No clear speech detected. Please try again.', 'warning');
            }
          } else {
            console.log('⚠️ No transcript in result[0]');
            ui.showNotification('Could not understand speech. Please try again.', 'warning');
          }
        } else {
          console.error('⚠️ No recognition results in event');
          ui.showNotification('Voice input failed. Please try again.', 'error');
        }
      };
      
      this.recognition.onerror = (event) => {
        console.error('🎤 Speech recognition error:', {
          error: event.error,
          message: event.message,
          timestamp: new Date().toISOString(),
          event: event
        });
        
        this.isRecording = false;
        this.updateVoiceButtonState(false);
        
        let errorMessage = 'Voice input failed. Please try again.';
        let shouldShowNotification = true;
        
        switch(event.error) {
          case 'not-allowed':
            errorMessage = 'Microphone access denied. Please allow microphone access in your browser settings and try again.';
            break;
          case 'no-speech':
            errorMessage = 'No speech detected. Please try speaking again.';
            break;
          case 'audio-capture':
            errorMessage = 'Microphone not available. Please check your microphone connection.';
            break;
          case 'network':
            errorMessage = 'Network error occurred during voice recognition. Please check your internet connection.';
            break;
          case 'service-not-allowed':
            errorMessage = 'Speech recognition service not allowed. Please check your browser settings.';
            break;
          case 'aborted':
            // Don't show notification for user-initiated stops
            shouldShowNotification = false;
            break;
          case 'bad-grammar':
            errorMessage = 'Speech recognition grammar error. Please try again.';
            break;
          case 'language-not-supported':
            errorMessage = 'Language not supported. Please check your browser settings.';
            break;
          default:
            errorMessage = `Voice input error (${event.error}). Please try refreshing the page.`;
            break;
        }
        
        console.error('🎤 Error message:', errorMessage);
        if (shouldShowNotification) {
          ui.showNotification(errorMessage, 'error');
        }
        };
      } else {
        console.log('🎤 Recognition object not available, skipping event handlers');
      }
    } else {
      console.log('🎤 Speech recognition not supported in this browser');
      // Hide voice button if not supported
      if (elements.voiceBtn) {
        elements.voiceBtn.style.display = 'none';
      }
    }
  },
  
  toggle() {
    if (this.isOpen) {
      this.close();
    } else {
      this.open();
    }
  },
  
  open() {
    this.isOpen = true;
    elements.assistantPanel.classList.add('active');
    document.body.classList.add('assistant-open');
    elements.assistantInput.focus();
    
    // Try to get weather data if not available
    if (!weather.lastWeatherData) {
      this.tryAutoWeatherFetch();
    }
    
    // Add welcome message if chat is empty
    if (elements.assistantChat.children.length === 0) {
      this.addMessage('assistant', 'Hello! I\'m your planning assistant. I can help you organize your tasks, provide productivity tips, and answer questions about your schedule. How can I help you today?');
    }
  },

  async tryAutoWeatherFetch() {
    console.log('🌤️ Attempting auto weather fetch...');
    
    // Check if we already have recent weather data
    if (weather.lastWeatherData && weather.lastWeatherData.current) {
      console.log('🌤️ Using existing weather data:', weather.lastWeatherData.current.condition);
      return;
    }
    
    try {
      // Try to get location and fetch weather automatically
      if (navigator.geolocation) {
        console.log('📍 Geolocation available, requesting position...');
        
        // Check if we have stored location from previous successful fetch
        const storedLocation = localStorage.getItem('weather_last_location');
        if (storedLocation) {
          try {
            const location = JSON.parse(storedLocation);
            console.log('📍 Using stored location:', location);
            const weatherData = await weather.getWeatherByCoordinates(location.latitude, location.longitude);
            weather.lastWeatherData = weatherData;
            console.log('🌤️ Successfully fetched weather using stored location');
            console.log('🌤️ Weather data:', weatherData);
            return;
          } catch (error) {
            console.warn('⚠️ Failed to use stored location, requesting fresh location');
          }
        }
        
        navigator.geolocation.getCurrentPosition(
          async (position) => {
            try {
              console.log('📍 Position obtained:', position.coords.latitude, position.coords.longitude);
              const weatherData = await weather.getWeatherByCoordinates(position.coords.latitude, position.coords.longitude);
              weather.lastWeatherData = weatherData;
              console.log('🌤️ Successfully auto-fetched weather data for assistant');
              console.log('🌤️ Weather data:', weatherData);
            } catch (error) {
              console.error('❌ Weather auto-fetch failed:', error);
            }
          },
          async (error) => {
            console.warn('⚠️ Location access denied:', error.message);
            console.log('🌤️ Weather will be limited without location access');
            
            // Try to use a default location for demo purposes
            console.log('🌤️ Attempting to use default location for weather...');
            try {
              const weatherData = await weather.getWeatherByCoordinates(40.7128, -74.0060); // NYC as fallback
              weather.lastWeatherData = weatherData;
              console.log('🌤️ Successfully fetched default location weather data');
            } catch (error) {
              console.error('❌ Default weather fetch failed:', error);
            }
          },
          { 
            timeout: 15000, 
            enableHighAccuracy: false,
            maximumAge: 300000 // 5 minutes
          }
        );
      } else {
        console.warn('⚠️ Geolocation not available in this browser');
        // Use default location
        console.log('🌤️ Using default location for weather...');
        const weatherData = await weather.getWeatherByCoordinates(40.7128, -74.0060); // NYC as fallback
        weather.lastWeatherData = weatherData;
        console.log('🌤️ Successfully fetched default location weather data');
      }
    } catch (error) {
      console.error('❌ Auto weather fetch error:', error);
    }
  },
  
  close() {
    this.isOpen = false;
    elements.assistantPanel.classList.remove('active');
    document.body.classList.remove('assistant-open');
    
    // Stop any ongoing recording
    if (this.isRecording && this.recognition) {
      this.recognition.stop();
    }
  },
  
  async sendMessage() {
    const message = elements.assistantInput.value.trim();
    if (!message) return;
    
    console.log('🚀 SENDING MESSAGE:', message);
    console.log('🕐 Timestamp:', new Date().toISOString());
    
    // Prevent duplicate calls
    if (this.isProcessing) {
      console.log('⚠️ Already processing a message, ignoring duplicate call');
      return;
    }
    this.isProcessing = true;
    
    // Add user message to chat
    this.addMessage('user', message);
    
    // Add to conversation history
    this.conversationHistory.push({
      sender: 'user',
      message: message,
      timestamp: new Date().toISOString()
    });
    
    elements.assistantInput.value = '';
    
    // Show typing indicator
    const typingId = this.addTypingIndicator();
    
    try {
      // Get user context (current tasks, day, etc.)
      const context = this.getUserContext();
      console.log('Context:', context);
      
      const response = await fetch('/api/assistant', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: message,
          context: context,
          conversationHistory: this.conversationHistory.slice(-10) // Send last 10 messages for context
        })
      });
      
      console.log('Response status:', response.status);
      
      if (!response.ok) {
        throw new Error('Failed to get assistant response');
      }
      
      const data = await response.json();
      console.log('📥 RESPONSE DATA:', data);
      
      // Check if response contains an error
      if (data.error) {
        console.error('💥 Response contains error:', data.error);
        throw new Error(data.error);
      }
      
      // Remove typing indicator
      this.removeTypingIndicator(typingId);
      
      console.log('💬 Adding assistant message:', data.response);
      // Add assistant response
      this.addMessage('assistant', data.response);
      
      // If tasks were created, add them to localStorage and refresh
      if (data.tasks && data.tasks.length > 0) {
        console.log(`🎯 Processing ${data.tasks.length} tasks from assistant...`);
        
        try {
          // Add each task to localStorage and Firebase - use Promise.all to wait for all saves
          const taskPromises = data.tasks.map(async (task, index) => {
            console.log(`🔄 Processing task ${index + 1}:`, task);
            
            // Use the day directly from the assistant (it should already be in the correct format)
            let dayName = task.day || state.currentDay;
            
            // Handle "Today" case
            if (dayName === 'Today') {
              dayName = state.currentDay;
            }
            
            // Handle weekOffset for future week tasks
            const taskWeekOffset = task.weekOffset || 0;
            
            // Create task in the expected format with Firebase ID
            const formattedTask = {
              id: task.id || utils.generateId(), // Use Firebase ID if available, or generate new one
              title: task.title,
              description: task.description || '',
              day: dayName,
              weekOffset: taskWeekOffset,
              time: task.startTime && task.endTime ? `${task.startTime}-${task.endTime}` : task.startTime || '09:00',
              startTime: task.startTime,
              endTime: task.endTime,
              priority: task.priority || 'medium',
              color: task.color || '#4ECDC4',
              completed: false,
              createdBy: 'assistant'
            };
            
            console.log(`➕ Adding task: ${formattedTask.title} on ${formattedTask.day} (week offset: ${taskWeekOffset}) (${formattedTask.time})`);
            return await tasks.createWithWeekOffset(formattedTask);
          });
          
          // Wait for all tasks to be saved to Firebase
          await Promise.all(taskPromises);
          console.log('✅ All assistant tasks saved to Firebase successfully');
          
          // Show success notification
          const taskWord = data.tasks.length === 1 ? 'task' : 'tasks';
          ui.showNotification(`✅ Created ${data.tasks.length} ${taskWord} for you!`, 'success');
          
          // Refresh the UI immediately with error handling
          try {
            tasks.render();
            calendar.renderTasks();
            ui.updateUI();
            console.log('✅ UI refresh completed successfully');
          } catch (uiError) {
            console.error('⚠️ UI refresh error (non-critical):', uiError);
            // Don't re-throw UI errors - they shouldn't break the assistant
          }
          
          console.log('✅ Task processing completed successfully');
        } catch (error) {
          console.error('❌ Error during task processing:', error);
          throw error; // Re-throw to trigger the catch block
        }
      }
      
      // If task actions were performed, process them
      if (data.taskActions && data.taskActions.length > 0) {
        console.log(`🔧 Processing ${data.taskActions.length} task actions from assistant...`);
        
        try {
          // Process each action to update local storage
          for (const action of data.taskActions) {
            console.log(`🔧 Processing action:`, action);
            
            // Safety checks to prevent undefined errors
            if (!action || typeof action !== 'object') {
              console.warn('⚠️ Invalid action object:', action);
              continue;
            }
            
            const taskTitle = action.task || 'Unknown Task';
            const taskId = action.taskId;
            const actionType = action.action;
            
            if (!actionType) {
              console.warn('⚠️ No action type specified:', action);
              continue;
            }
            
            // Update local storage to match Firebase changes
            if (actionType === 'deleted') {
              if (taskId) {
                // Use task ID for precise deletion
                console.log(`🔍 Deleting task by ID: ${taskId}`);
                let tasksRemoved = 0;
                
                // Ensure state.tasks exists
                if (state.tasks && typeof state.tasks === 'object') {
                  for (const weekKey in state.tasks) {
                    if (Array.isArray(state.tasks[weekKey])) {
                      const beforeCount = state.tasks[weekKey].length;
                      state.tasks[weekKey] = state.tasks[weekKey].filter(task => {
                        if (task && task.id === taskId) {
                          console.log(`🎯 Found and removing task: "${task.title}" (ID: ${task.id})`);
                          tasksRemoved++;
                          return false; // Remove this task
                        }
                        return true; // Keep this task
                      });
                      
                      const afterCount = state.tasks[weekKey].length;
                      if (beforeCount !== afterCount) {
                        console.log(`📋 Week ${weekKey}: ${beforeCount} → ${afterCount} tasks`);
                      }
                    }
                  }
                }
                
                if (tasksRemoved > 0) {
                  console.log(`🗑️ Successfully removed task with ID ${taskId} from local storage`);
                } else {
                  console.log(`⚠️ Task with ID ${taskId} not found in local storage (may have been assistant-created)`);
                }
              } else {
                // Fallback to title matching (less precise)
                console.log(`⚠️ No task ID provided, falling back to title search: "${taskTitle}"`);
                let tasksRemoved = 0;
                
                for (const weekKey in state.tasks) {
                  state.tasks[weekKey] = state.tasks[weekKey].filter(task => {
                    const taskTitleLower = task.title.toLowerCase().trim();
                    const searchTitleLower = taskTitle.toLowerCase().trim();
                    
                    if (taskTitleLower === searchTitleLower) {
                      console.log(`🎯 Found matching task to delete: "${task.title}"`);
                      tasksRemoved++;
                      return false; // Remove this task
                    }
                    return true; // Keep this task
                  });
                }
                
                console.log(`�️ Removed ${tasksRemoved} task(s) by title matching`);
              }
            } else if (actionType === 'completed') {
              if (taskId) {
                // Use task ID for precise updates
                if (state.tasks && typeof state.tasks === 'object') {
                  for (const weekKey in state.tasks) {
                    if (Array.isArray(state.tasks[weekKey])) {
                      const task = state.tasks[weekKey].find(task => task && task.id === taskId);
                      if (task) {
                        task.completed = true;
                        task.completedAt = new Date().toISOString();
                        console.log(`✅ Marked task ID ${taskId} as completed in local storage`);
                        break;
                      }
                    }
                  }
                }
              } else {
                // Fallback to title matching
                if (state.tasks && typeof state.tasks === 'object') {
                  for (const weekKey in state.tasks) {
                    if (Array.isArray(state.tasks[weekKey])) {
                      const task = state.tasks[weekKey].find(task => 
                        task && task.title && task.title.toLowerCase().includes(taskTitle.toLowerCase())
                      );
                      if (task) {
                        task.completed = true;
                        task.completedAt = new Date().toISOString();
                        console.log(`✅ Marked '${taskTitle}' as completed in local storage`);
                        break;
                      }
                    }
                  }
                }
              }
            } else if (actionType === 'uncompleted') {
              if (taskId) {
                // Use task ID for precise updates
                if (state.tasks && typeof state.tasks === 'object') {
                  for (const weekKey in state.tasks) {
                    if (Array.isArray(state.tasks[weekKey])) {
                      const task = state.tasks[weekKey].find(task => task && task.id === taskId);
                      if (task) {
                        task.completed = false;
                        delete task.completedAt;
                        console.log(`↩️ Marked task ID ${taskId} as uncompleted in local storage`);
                        break;
                      }
                    }
                  }
                }
              } else {
                // Fallback to title matching
                if (state.tasks && typeof state.tasks === 'object') {
                  for (const weekKey in state.tasks) {
                    if (Array.isArray(state.tasks[weekKey])) {
                      const task = state.tasks[weekKey].find(task => 
                        task && task.title && task.title.toLowerCase().includes(taskTitle.toLowerCase())
                      );
                      if (task) {
                        task.completed = false;
                        delete task.completedAt;
                        console.log(`↩️ Marked '${taskTitle}' as uncompleted in local storage`);
                        break;
                      }
                    }
                  }
                }
              }
            } else if (actionType === 'edited' && action.changes) {
              if (taskId) {
                // Use task ID for precise updates
                if (state.tasks && typeof state.tasks === 'object') {
                  for (const weekKey in state.tasks) {
                    if (Array.isArray(state.tasks[weekKey])) {
                      const taskIndex = state.tasks[weekKey].findIndex(task => task && task.id === taskId);
                      if (taskIndex !== -1) {
                        state.tasks[weekKey][taskIndex] = {
                          ...state.tasks[weekKey][taskIndex],
                          ...action.changes,
                          updatedAt: new Date().toISOString()
                        };
                        console.log(`✏️ Updated task ID ${taskId} with changes:`, action.changes);
                        break;
                      }
                    }
                  }
                }
              } else {
                // Fallback to title matching
                if (state.tasks && typeof state.tasks === 'object') {
                  for (const weekKey in state.tasks) {
                    if (Array.isArray(state.tasks[weekKey])) {
                      const task = state.tasks[weekKey].find(task => 
                        task && task.title && task.title.toLowerCase().includes(taskTitle.toLowerCase())
                      );
                      if (task) {
                        Object.assign(task, action.changes);
                        console.log(`✏️ Updated '${taskTitle}' in local storage:`, action.changes);
                        break;
                      }
                    }
                  }
                }
              }
            }
          }
          
          // Save updated state to local storage
          utils.saveToLocalStorage();
          
          // Immediately update UI with local changes
          tasks.render();
          if (elements.calendarModal.classList.contains('active')) {
            calendar.render();
          }
          ui.updateUI();
          
          console.log('🎨 UI updated immediately after task actions');
          
          // Then refresh from Firebase in background to ensure consistency
          setTimeout(async () => {
            try {
              await utils.refreshTasksFromFirebase();
              console.log('✅ Background Firebase sync completed after task actions');
            } catch (refreshError) {
              console.error('⚠️ Background Firebase refresh failed:', refreshError);
              // Don't show this error to user since main actions completed successfully
            }
          }, 500);
          
          // Show success notification
          const actionWord = data.taskActions.length === 1 ? 'action' : 'actions';
          ui.showNotification(`✅ Performed ${data.taskActions.length} task ${actionWord} for you!`, 'success');
          
          console.log('✅ Task actions processing completed successfully');
        } catch (error) {
          console.error('❌ Error during task actions processing:', error);
          // Don't re-throw - task action errors shouldn't fail the entire response
          ui.showNotification('Some task actions may not have completed successfully', 'warning');
        }
      }
      
    } catch (error) {
      console.error('❌ ASSISTANT ERROR:', error);
      console.error('Error details:', {
        message: error.message,
        stack: error.stack,
        timestamp: new Date().toISOString()
      });
      this.removeTypingIndicator(typingId);
      this.addMessage('assistant', 'Sorry, I\'m having trouble connecting right now. Please try again in a moment.');
    } finally {
      // Always reset processing flag
      this.isProcessing = false;
      console.log('✅ Message processing complete');
    }
  },
  
  addMessage(sender, content) {
    // Add to conversation history (but only for assistant messages, user messages are added in sendMessage)
    if (sender === 'assistant') {
      this.conversationHistory.push({
        sender: 'assistant',
        message: content,
        timestamp: new Date().toISOString()
      });
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('chat-message', sender);
    
    const avatar = document.createElement('div');
    avatar.classList.add('message-avatar');
    avatar.innerHTML = sender === 'user' ? 
      '<i class="fas fa-user"></i>' : 
      '<i class="fas fa-robot"></i>';
    
    const messageContent = document.createElement('div');
    messageContent.classList.add('message-content');
    messageContent.textContent = content;
    
    const timestamp = document.createElement('div');
    timestamp.classList.add('message-timestamp');
    timestamp.textContent = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(messageContent);
    messageDiv.appendChild(timestamp);
    
    elements.assistantChat.appendChild(messageDiv);
    elements.assistantChat.scrollTop = elements.assistantChat.scrollHeight;
  },
  
  addTypingIndicator() {
    const typingDiv = document.createElement('div');
    typingDiv.classList.add('chat-message', 'assistant', 'typing');
    
    const avatar = document.createElement('div');
    avatar.classList.add('message-avatar');
    avatar.innerHTML = '<i class="fas fa-robot"></i>';
    
    const messageContent = document.createElement('div');
    messageContent.classList.add('message-content');
    messageContent.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
    
    typingDiv.appendChild(avatar);
    typingDiv.appendChild(messageContent);
    
    elements.assistantChat.appendChild(typingDiv);
    elements.assistantChat.scrollTop = elements.assistantChat.scrollHeight;
    
    return typingDiv;
  },
  
  removeTypingIndicator(typingElement) {
    if (typingElement && typingElement.parentNode) {
      typingElement.parentNode.removeChild(typingElement);
    }
  },
  
  getUserContext() {
    const today = new Date();
    const weekKey = utils.getWeekKey(state.currentDay);
    const dayTasks = state.tasks[weekKey] || [];
    
    // Get current day name
    const dayNames = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
    const actualToday = dayNames[today.getDay()];
    
    // Get weather information with better forecasting
    let weatherInfo = null;
    if (weather.lastWeatherData) {
      const isToday = state.currentDay === actualToday;
      
      if (isToday && weather.lastWeatherData.current) {
        // Current day weather
        weatherInfo = {
          condition: weather.lastWeatherData.current.condition,
          temperature: weather.lastWeatherData.current.temperature,
          description: weather.lastWeatherData.current.description,
          location: weather.lastWeatherData.current.location,
          isRaining: weather.lastWeatherData.current.condition && 
                    weather.lastWeatherData.current.condition.toLowerCase().includes('rain'),
          isSnowing: weather.lastWeatherData.current.condition && 
                    weather.lastWeatherData.current.condition.toLowerCase().includes('snow'),
          isCloudy: weather.lastWeatherData.current.condition && 
                   (weather.lastWeatherData.current.condition.toLowerCase().includes('cloud') ||
                    weather.lastWeatherData.current.condition.toLowerCase().includes('overcast')),
          isSunny: weather.lastWeatherData.current.condition && 
                  (weather.lastWeatherData.current.condition.toLowerCase().includes('sun') ||
                   weather.lastWeatherData.current.condition.toLowerCase().includes('clear')),
          isCurrentDay: true
        };
      } else if (weather.lastWeatherData.forecast) {
        // Find forecast for the selected day
        const forecast = weather.lastWeatherData.forecast.find(f => f.day === state.currentDay);
        if (forecast) {
          weatherInfo = {
            condition: forecast.condition,
            highTemp: forecast.high_temp || forecast.high,
            lowTemp: forecast.low_temp || forecast.low,
            temperature: forecast.high_temp || forecast.high, // Use high temp as main temperature
            description: forecast.description || forecast.condition,
            location: weather.lastWeatherData.current?.location || 'your location',
            isRaining: forecast.condition && forecast.condition.toLowerCase().includes('rain'),
            isSnowing: forecast.condition && forecast.condition.toLowerCase().includes('snow'),
            isCloudy: forecast.condition && 
                     (forecast.condition.toLowerCase().includes('cloud') ||
                      forecast.condition.toLowerCase().includes('overcast')),
            isSunny: forecast.condition && 
                    (forecast.condition.toLowerCase().includes('sun') ||
                     forecast.condition.toLowerCase().includes('clear')),
            isCurrentDay: false,
            isForecast: true
          };
        }
      }
      
      // If no weather found for specific day, provide general forecast info
      if (!weatherInfo && weather.lastWeatherData.forecast && weather.lastWeatherData.forecast.length > 0) {
        weatherInfo = {
          condition: "Forecast available",
          description: `Weather forecast available for ${weather.lastWeatherData.forecast.length} days`,
          location: weather.lastWeatherData.current?.location || 'your location',
          hasGeneralForecast: true,
          forecastDays: weather.lastWeatherData.forecast.map(f => ({
            day: f.day,
            condition: f.condition,
            high: f.high_temp || f.high,
            low: f.low_temp || f.low
          }))
        };
      }
    }
    
    return {
      currentDay: state.currentDay,
      currentDate: today.toDateString(),
      currentTime: today.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true }), // e.g., "10:49 AM"
      currentHour: today.getHours(), // 0-23
      actualToday: actualToday, // The actual current day name
      weekOffset: state.weekOffset,
      tasksToday: dayTasks.length,
      completedToday: dayTasks.filter(task => task.completed).length,
      upcomingTasks: dayTasks.filter(task => !task.completed).map(task => ({
        id: task.id,
        title: task.title,
        time: task.time,
        priority: task.priority,
        description: task.description
      })),
      totalTasksThisWeek: dayTasks.length,
      weather: weatherInfo
    };
  },
  
  async startVoiceInput() {
    console.log('🎤 startVoiceInput called');
    console.log('🎤 Recognition exists:', !!this.recognition);
    console.log('🎤 Currently recording:', this.isRecording);
    console.log('🎤 Browser:', navigator.userAgent.substring(0, 100));
    console.log('🎤 Protocol:', location.protocol);
    console.log('🎤 Host:', location.host);
    
    // Check if we're on HTTPS or localhost
    const isSecureContext = location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1';
    console.log('🎤 Secure context:', isSecureContext);
    
    if (!isSecureContext) {
      console.error('🎤 Speech recognition requires HTTPS or localhost');
      ui.showNotification('Voice input requires HTTPS or localhost. Please use a secure connection.', 'error');
      return;
    }
    
    if (!this.recognition) {
      console.error('🎤 No recognition object available');
      ui.showNotification('Voice input is not supported in your browser. Please use Chrome or Edge.', 'error');
      return;
    }
    
    if (this.isRecording) {
      console.log('🎤 Stopping voice input');
      try {
        this.recognition.stop();
      } catch (error) {
        console.error('🎤 Error stopping recognition:', error);
        this.isRecording = false;
        this.updateVoiceButtonState(false);
      }
      return;
    }

    try {
      // Check microphone permissions first
      console.log('🎤 Checking microphone permissions...');
      
      if (navigator.permissions) {
        try {
          const permissionStatus = await navigator.permissions.query({ name: 'microphone' });
          console.log('🎤 Microphone permission status:', permissionStatus.state);
          
          if (permissionStatus.state === 'denied') {
            ui.showNotification('Microphone access is blocked. Please allow microphone access in your browser settings.', 'error');
            return;
          }
        } catch (permError) {
          console.log('🎤 Could not check permissions (not critical):', permError.message);
        }
      }
      
      console.log('🎤 Starting speech recognition...');
      console.log('🎤 Recognition properties:', {
        continuous: this.recognition.continuous,
        interimResults: this.recognition.interimResults,
        lang: this.recognition.lang,
        maxAlternatives: this.recognition.maxAlternatives
      });
      
      this.recognition.start();
      console.log('🎤 Recognition.start() called successfully');
      
    } catch (error) {
      console.error('🎤 Failed to start speech recognition:', error);
      console.error('🎤 Error details:', {
        name: error.name,
        message: error.message,
        stack: error.stack
      });
      
      let errorMessage = 'Voice input failed. ';
      if (error.name === 'NotAllowedError') {
        errorMessage += 'Please allow microphone access and try again.';
      } else if (error.name === 'NotSupportedError') {
        errorMessage += 'Your browser does not support voice input.';
      } else {
        errorMessage += `${error.message}. Try refreshing the page.`;
      }
      
      ui.showNotification(errorMessage, 'error');
      this.updateVoiceButtonState(false);
    }
  },
  
  updateVoiceButtonState(isRecording) {
    if (!elements.voiceBtn) return;
    
    if (isRecording) {
      elements.voiceBtn.classList.add('recording');
      elements.voiceBtn.title = 'Stop recording';
      const svg = elements.voiceBtn.querySelector('svg');
      if (svg) {
        svg.innerHTML = '<rect x="6" y="6" width="12" height="12" fill="currentColor"></rect>';
      }
    } else {
      elements.voiceBtn.classList.remove('recording');
      elements.voiceBtn.title = 'Start voice input';
      const svg = elements.voiceBtn.querySelector('svg');
      if (svg) {
        svg.innerHTML = '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line>';
      }
    }
  },

  // ===== Task Management Methods for Assistant =====
  
  async deleteTask(taskId, reason = 'Assistant deleted task') {
    try {
      console.log(`🗑️ Assistant deleting task: ${taskId}`);
      const success = await tasks.delete(taskId);
      if (success) {
        tasks.render();
        if (elements.calendarModal.classList.contains('active')) {
          calendar.render();
        }
        console.log(`✅ Assistant successfully deleted task: ${taskId}`);
        return { success: true, message: `Task deleted successfully. ${reason}` };
      } else {
        console.log(`❌ Assistant failed to find task: ${taskId}`);
        return { success: false, message: 'Task not found' };
      }
    } catch (error) {
      console.error('❌ Assistant task deletion error:', error);
      return { success: false, message: `Failed to delete task: ${error.message}` };
    }
  },

  async deleteTasksByTitle(title, reason = 'Assistant deleted tasks') {
    try {
      console.log(`🗑️ Assistant deleting tasks by title: "${title}"`);
      let deletedCount = 0;
      const tasksToDelete = [];
      
      // Find all tasks with matching title (more precise matching)
      for (const weekKey in state.tasks) {
        const weekTasks = state.tasks[weekKey];
        for (const task of weekTasks) {
          const taskTitle = task.title.toLowerCase().trim();
          const searchTitle = title.toLowerCase().trim();
          
          // More precise matching: exact match, starts with, or contains (only if >3 chars)
          if (taskTitle === searchTitle || 
              taskTitle.startsWith(searchTitle) ||
              (searchTitle.length > 3 && taskTitle.includes(searchTitle))) {
            tasksToDelete.push(task.id);
            
            // Safety limit: prevent mass deletion
            if (tasksToDelete.length >= 3) {
              console.log(`⚠️ Limiting deletion to 3 tasks to prevent accidents`);
              break;
            }
          }
        }
        if (tasksToDelete.length >= 3) break;
      }
      
      console.log(`📋 Found ${tasksToDelete.length} tasks to delete:`, tasksToDelete);
      
      // Delete each matching task
      for (const taskId of tasksToDelete) {
        const result = await this.deleteTask(taskId, reason);
        if (result.success) {
          deletedCount++;
        }
      }
      
      console.log(`✅ Assistant deleted ${deletedCount} tasks with title containing "${title}"`);
      return { 
        success: true, 
        message: `Deleted ${deletedCount} task${deletedCount !== 1 ? 's' : ''} containing "${title}". ${reason}`,
        deletedCount 
      };
    } catch (error) {
      console.error('❌ Assistant bulk deletion error:', error);
      return { success: false, message: `Failed to delete tasks: ${error.message}` };
    }
  },

  async editTask(taskId, updates, reason = 'Assistant updated task') {
    try {
      console.log(`✏️ Assistant editing task: ${taskId}`, updates);
      
      // Find the task
      let taskFound = false;
      for (const weekKey in state.tasks) {
        const task = state.tasks[weekKey].find(t => t.id === taskId);
        if (task) {
          // Update the task properties
          Object.keys(updates).forEach(key => {
            if (updates[key] !== undefined) {
              task[key] = updates[key];
            }
          });
          
          // Save to local storage
          utils.saveToLocalStorage();
          
          // Save to Firebase
          try {
            await utils.makeApiCall(`/api/tasks/${taskId}`, 'PUT', updates);
            console.log('✅ Task updated in Firebase');
          } catch (error) {
            console.error('⚠️ Failed to update task in Firebase:', error);
          }
          
          // Update UI
          tasks.render();
          if (elements.calendarModal.classList.contains('active')) {
            calendar.render();
          }
          
          taskFound = true;
          break;
        }
      }
      
      if (taskFound) {
        console.log(`✅ Assistant successfully updated task: ${taskId}`);
        return { success: true, message: `Task updated successfully. ${reason}` };
      } else {
        console.log(`❌ Assistant failed to find task: ${taskId}`);
        return { success: false, message: 'Task not found' };
      }
    } catch (error) {
      console.error('❌ Assistant task editing error:', error);
      return { success: false, message: `Failed to edit task: ${error.message}` };
    }
  },

  async editTasksByTitle(title, updates, reason = 'Assistant updated tasks') {
    try {
      console.log(`✏️ Assistant editing tasks by title: "${title}"`, updates);
      let updatedCount = 0;
      
      // Find and update all tasks with matching title (case-insensitive)
      for (const weekKey in state.tasks) {
        const weekTasks = state.tasks[weekKey];
        for (const task of weekTasks) {
          if (task.title.toLowerCase().includes(title.toLowerCase())) {
            const result = await this.editTask(task.id, updates, reason);
            if (result.success) {
              updatedCount++;
            }
          }
        }
      }
      
      console.log(`✅ Assistant updated ${updatedCount} tasks with title containing "${title}"`);
      return { 
        success: true, 
        message: `Updated ${updatedCount} task${updatedCount !== 1 ? 's' : ''} containing "${title}". ${reason}`,
        updatedCount 
      };
    } catch (error) {
      console.error('❌ Assistant bulk editing error:', error);
      return { success: false, message: `Failed to edit tasks: ${error.message}` };
    }
  },

  async completeTask(taskId, reason = 'Assistant marked task as complete') {
    try {
      const result = await this.editTask(taskId, { 
        completed: true, 
        completedAt: new Date().toISOString() 
      }, reason);
      return result;
    } catch (error) {
      return { success: false, message: `Failed to complete task: ${error.message}` };
    }
  },

  async uncompleteTask(taskId, reason = 'Assistant marked task as incomplete') {
    try {
      const result = await this.editTask(taskId, { 
        completed: false, 
        completedAt: null 
      }, reason);
      return result;
    } catch (error) {
      return { success: false, message: `Failed to uncomplete task: ${error.message}` };
    }
  },

  // Get all tasks for assistant to reference
  getAllTasks() {
    const allTasks = [];
    for (const weekKey in state.tasks) {
      const weekTasks = state.tasks[weekKey];
      weekTasks.forEach(task => {
        allTasks.push({
          id: task.id,
          title: task.title,
          description: task.description,
          day: task.day,
          time: task.time,
          priority: task.priority,
          completed: task.completed,
          createdAt: task.createdAt,
          weekKey: weekKey
        });
      });
    }
    return allTasks;
  }
};

// ===== Event Handlers =====
const initEventHandlers = () => {
  // Sidebar toggle
  elements.sidebarToggle.addEventListener('click', () => {
    elements.sidebar.classList.toggle('collapsed');
  });

  // Settings button
  elements.settingsBtn.addEventListener('click', () => {
    notifications.loadSettings();
    ui.openModal(elements.settingsModal);
  });

  // Weather button
  elements.weatherBtn.addEventListener('click', () => {
    weather.showModal();
  });

  // Weather modal handlers
  const allowLocationBtn = document.getElementById('allow-location-btn');
  if (allowLocationBtn) {
    allowLocationBtn.addEventListener('click', async () => {
      // Show loading state immediately when user clicks allow location
      const locationEl = document.getElementById('location-request');
      const loadingEl = document.getElementById('weather-loading');
      const dataEl = document.getElementById('weather-data');
      const errorEl = document.getElementById('weather-error');
      
      // Hide location request and show loading
      locationEl.style.display = 'none';
      loadingEl.style.display = 'block';
      dataEl.style.display = 'none';
      errorEl.style.display = 'none';
      
      // Update loading text to show location request
      const loadingText = loadingEl.querySelector('p');
      if (loadingText) {
        loadingText.textContent = 'Requesting location access...';
      }
      
      try {
        console.log('🌍 Requesting location access...');
        await weather.requestLocation();
        
        // Update loading text to show weather fetch
        if (loadingText) {
          loadingText.textContent = 'Loading weather data...';
        }
        
        console.log('🌤️ Loading weather data...');
        await weather.loadWeatherData();
        
        console.log('✅ Weather data loaded successfully');
      } catch (error) {
        console.error('❌ Weather loading failed:', error);
        weather.showError(error.message);
        
        // Show error state
        locationEl.style.display = 'none';
        loadingEl.style.display = 'none';
        dataEl.style.display = 'none';
        errorEl.style.display = 'block';
      }
    });
  }

  const manualSearchBtn = document.getElementById('manual-search-btn');
  const manualCityInput = document.getElementById('manual-city-input');
  if (manualSearchBtn && manualCityInput) {
    // Setup autocomplete for manual search input
    weather.setupAutocomplete('manual-city-input', 'manual-autocomplete-dropdown');
    
    manualSearchBtn.addEventListener('click', () => {
      weather.searchCity(manualCityInput.value);
    });
    
    manualCityInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        weather.searchCity(manualCityInput.value);
      }
    });
  }

  const refreshWeatherBtn = document.getElementById('refresh-weather-btn');
  if (refreshWeatherBtn) {
    refreshWeatherBtn.addEventListener('click', () => {
      weather.refreshWeather();
    });
  }

  // Top weather search (always visible)
  const weatherSearchBtn = document.getElementById('weather-search-btn');
  const weatherCitySearch = document.getElementById('weather-city-search');
  if (weatherSearchBtn && weatherCitySearch) {
    // Setup autocomplete for main weather search
    weather.setupAutocomplete('weather-city-search', 'weather-search-dropdown');
    
    weatherSearchBtn.addEventListener('click', () => {
      weather.searchCity(weatherCitySearch.value);
    });
    
    weatherCitySearch.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        weather.searchCity(weatherCitySearch.value);
      }
    });
  }

  const retryWeatherBtn = document.getElementById('retry-weather-btn');
  if (retryWeatherBtn) {
    retryWeatherBtn.addEventListener('click', () => {
      weather.showModal();
    });
  }

  // Assistant handlers
  if (elements.fabAssistant) {
    elements.fabAssistant.addEventListener('click', () => {
      console.log('Assistant button clicked!'); // Keep this one for testing
      assistant.toggle();
    });
  }

  if (elements.assistantClose) {
    elements.assistantClose.addEventListener('click', () => {
      assistant.close();
    });
  }

  if (elements.assistantSend) {
    elements.assistantSend.addEventListener('click', (e) => {
      console.log('🖱️ Send button clicked');
      e.preventDefault();
      assistant.sendMessage();
    });
  }

  if (elements.assistantInput) {
    elements.assistantInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        console.log('⌨️ Enter key pressed');
        e.preventDefault();
        assistant.sendMessage();
      }
    });
  }

  if (elements.voiceBtn) {
    elements.voiceBtn.addEventListener('click', () => {
      assistant.startVoiceInput();
    });
  }

  // Welcome suggestions
  const welcomeSuggestions = document.querySelectorAll('.welcome-suggestions li');
  welcomeSuggestions.forEach(suggestion => {
    suggestion.addEventListener('click', () => {
      elements.assistantInput.value = suggestion.textContent;
      assistant.sendMessage();
    });
  });

  // Enhanced Settings UI - Single Page Design
  const notificationsEnabledCheckbox = document.getElementById('notifications-enabled');
  const settingsContent = document.getElementById('settings-content');
  const notificationStatus = document.getElementById('notification-status');
  
  if (notificationsEnabledCheckbox && settingsContent && notificationStatus) {
    // Set initial state
    notificationsEnabledCheckbox.checked = state.userSettings.notifications_enabled;
    settingsContent.style.display = state.userSettings.notifications_enabled ? 'block' : 'none';
    
    // Update status indicator
    const updateStatus = (enabled) => {
      const statusIndicator = notificationStatus.querySelector('.status-indicator');
      const statusText = notificationStatus.querySelector('.status-text');
      
      if (statusIndicator && statusText) {
        if (enabled) {
          statusIndicator.classList.add('active');
          statusText.textContent = 'Notifications active';
        } else {
          statusIndicator.classList.remove('active');
          statusText.textContent = 'Notifications disabled';
        }
      }
    };
    
    // Initial status update
    updateStatus(state.userSettings.notifications_enabled);
    
    notificationsEnabledCheckbox.addEventListener('change', async (e) => {
      state.userSettings.notifications_enabled = e.target.checked;
      
      if (e.target.checked) {
        settingsContent.style.display = 'block';
        settingsContent.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        ui.showNotification('🔔 Smart notifications enabled! Configure your preferences below.', 'success');
        
        // Initialize notification scheduler
        await notificationScheduler.init();
      } else {
        settingsContent.style.display = 'none';
        ui.showNotification('🔕 Notifications disabled', 'info');
        
        // Clear all scheduled notifications
        notificationScheduler.scheduledNotifications.forEach(timeoutId => {
          clearTimeout(timeoutId);
        });
        notificationScheduler.scheduledNotifications.clear();
        if (notificationScheduler.dailySummaryTimer) {
          clearTimeout(notificationScheduler.dailySummaryTimer);
        }
      }
      
      updateStatus(e.target.checked);
      notifications.updateUI();
      
      // Save the setting to persist it (no notification for toggle)
      notifications.saveSettings(false);
    });
  }

  // Contact Information
  const emailInput = document.getElementById('notification-email');
  if (emailInput) {
    emailInput.addEventListener('input', (e) => {
      state.userSettings.email = e.target.value;
      // Add validation indicator
      const statusElement = document.getElementById('email-status');
      if (statusElement) {
        const isValid = e.target.value && e.target.value.includes('@');
        statusElement.textContent = isValid ? '✓' : '';
        statusElement.style.color = isValid ? 'var(--success)' : '';
      }
    });
  }

  const phoneInput = document.getElementById('phone-number');
  if (phoneInput) {
    phoneInput.addEventListener('input', (e) => {
      state.userSettings.phone = e.target.value;
      // Add validation indicator
      const statusElement = document.getElementById('phone-status');
      if (statusElement) {
        const isValid = e.target.value && e.target.value.length >= 10;
        statusElement.textContent = isValid ? '✓' : '';
        statusElement.style.color = isValid ? 'var(--success)' : '';
      }
    });
  }

  // Multiple notification methods support
  const methodCheckboxes = document.querySelectorAll('input[name="notification-methods"]');
  methodCheckboxes.forEach(checkbox => {
    checkbox.addEventListener('change', () => {
      // Get all selected methods
      const selectedMethods = Array.from(methodCheckboxes)
        .filter(cb => cb.checked)
        .map(cb => cb.value);
      
      // Store as array instead of single value
      state.userSettings.notification_methods = selectedMethods;
      
      // For backward compatibility, set primary method to first selected
      state.userSettings.notification_method = selectedMethods[0] || 'email';
      
      notifications.updateUI();
    });
  });

  const dailySummaryCheckbox = document.getElementById('daily-summary');
  if (dailySummaryCheckbox) {
    dailySummaryCheckbox.addEventListener('change', (e) => {
      state.userSettings.daily_summary = e.target.checked;
    });
  }

  const reminderTimeSelect = document.getElementById('reminder-time');
  if (reminderTimeSelect) {
    reminderTimeSelect.addEventListener('change', (e) => {
      state.userSettings.reminder_time = parseInt(e.target.value);
    });
  }

  const autoInspirationCheckbox = document.getElementById('auto-inspiration');
  if (autoInspirationCheckbox) {
    autoInspirationCheckbox.addEventListener('change', (e) => {
      state.userSettings.auto_inspiration = e.target.checked;
    });
  }

  // Cleanup settings
  const autoCleanupCheckbox = document.getElementById('auto-cleanup');
  const cleanupWeeksSetting = document.getElementById('cleanup-weeks-setting');
  const cleanupWeeksSelect = document.getElementById('cleanup-weeks');
  
  if (autoCleanupCheckbox) {
    autoCleanupCheckbox.addEventListener('change', async (e) => {
      state.userSettings.auto_cleanup = e.target.checked;
      state.userSettings.auto_delete_old_tasks = e.target.checked; // Keep both for compatibility
      
      if (cleanupWeeksSetting) {
        cleanupWeeksSetting.style.display = e.target.checked ? 'flex' : 'none';
      }
      
      // Save to database instead of just localStorage
      await notifications.saveSettings(false);
      
      if (e.target.checked) {
        ui.showNotification('🗑️ Auto-cleanup enabled! Old tasks will be deleted automatically.', 'success');
        // Run cleanup immediately when enabled
        tasks.deleteOldTasks();
      } else {
        ui.showNotification('Auto-cleanup disabled', 'info');
      }
    });
  }
  
  if (cleanupWeeksSelect) {
    cleanupWeeksSelect.addEventListener('change', async (e) => {
      state.userSettings.cleanup_weeks = parseInt(e.target.value);
      
      // Save to database instead of just localStorage
      await notifications.saveSettings(false);
      
      ui.showNotification(`Cleanup period set to ${e.target.value} weeks`, 'success');
    });
  }

  const saveSettingsBtn = document.getElementById('save-settings-btn');
  if (saveSettingsBtn) {
    saveSettingsBtn.addEventListener('click', () => {
      notifications.saveSettings(true); // Show notification for manual save
    });
  }

  const signOutBtn = document.getElementById('sign-out-btn');
  if (signOutBtn) {
    signOutBtn.addEventListener('click', async () => {
      const confirmed = await ui.showConfirmation({
        title: 'Sign Out',
        message: 'Are you sure you want to sign out? You will need to log in again to access your planner.',
        confirmText: 'Sign Out',
        cancelText: 'Cancel',
        type: 'warning'
      });
      
      if (confirmed) {
        // Show notification
        ui.showNotification('Signing out...', 'success');
        
        // Redirect to logout endpoint which will handle Firebase sign-out
        // and clear all authentication data
        setTimeout(() => {
          window.location.href = '/logout';
        }, 500);
      }
    });
  }

  const testNotificationBtn = document.getElementById('test-notification-btn');
  if (testNotificationBtn) {
    testNotificationBtn.addEventListener('click', async () => {
      console.log('🧪 Test notification button clicked');
      
      // Update test status
      const testResult = document.getElementById('test-result');
      const lastTestTime = document.getElementById('last-test-time');
      
      if (testResult) testResult.textContent = 'Testing...';
      
      try {
        await notifications.sendTestNotification();
        if (testResult) testResult.textContent = 'Test successful';
        if (lastTestTime) lastTestTime.textContent = new Date().toLocaleTimeString();
      } catch (error) {
        if (testResult) testResult.textContent = 'Test failed';
      }
    });
  }
  
  const testTaskReminderBtn = document.getElementById('test-task-reminder-btn');
  if (testTaskReminderBtn) {
    testTaskReminderBtn.addEventListener('click', async () => {
      console.log('⏰ Test task reminder button clicked');
      try {
        ui.showNotification('Sending test task reminder...', 'info');
        const response = await utils.makeApiCall('/api/test-task-reminder', 'POST');
        
        if (response.status === 'success') {
          ui.showNotification(response.message, 'success');
        } else {
          ui.showNotification('Test task reminder sent!', 'success');
        }
      } catch (error) {
        console.error('❌ Failed to send test task reminder:', error);
        const errorMessage = error.response?.error || 'Failed to send test task reminder';
        ui.showNotification(errorMessage, 'error');
      }
    });
  }
  
  const testDailySummaryBtn = document.getElementById('test-daily-summary-btn');
  if (testDailySummaryBtn) {
    testDailySummaryBtn.addEventListener('click', async () => {
      console.log('📊 Test daily summary button clicked');
      try {
        ui.showNotification('Sending test daily summary...', 'info');
        const response = await utils.makeApiCall('/api/test-daily-summary', 'POST');
        
        if (response.status === 'success') {
          ui.showNotification(response.message, 'success');
        } else {
          ui.showNotification('Test daily summary sent!', 'success');
        }
      } catch (error) {
        console.error('❌ Failed to send test daily summary:', error);
        const errorMessage = error.response?.error || 'Failed to send test daily summary';
        ui.showNotification(errorMessage, 'error');
      }
    });
  }

  const sendInspirationBtn = document.getElementById('send-inspiration-btn');
  if (sendInspirationBtn) {
    sendInspirationBtn.addEventListener('click', () => {
      console.log('💫 Send inspiration button clicked');
      notifications.sendInspiration();
    });
  }

  // Delete all today button
  const deleteAllBtn = document.getElementById('delete-all-today-btn');
  if (deleteAllBtn) {
    deleteAllBtn.addEventListener('click', () => {
      tasks.deleteAllToday();
    });
  }


  // Day selection
  elements.daysList.querySelectorAll('.day-item').forEach(item => {
    item.addEventListener('click', () => {
      ui.setCurrentDay(item.dataset.day);
    });
    
    // Drag and drop
    item.addEventListener('dragover', (e) => {
      e.preventDefault();
      item.classList.add('dragover');
    });
    
    item.addEventListener('dragleave', () => {
      item.classList.remove('dragover');
    });
    
    item.addEventListener('drop', (e) => {
      e.preventDefault();
      item.classList.remove('dragover');
      
      if (state.draggedTask) {
        const newDay = item.dataset.day;
        const oldWeekKey = utils.getWeekKey(state.draggedTask.day);
        const newWeekKey = utils.getWeekKey(newDay);
        
        const oldTasks = state.tasks[oldWeekKey];
        if (oldTasks) {
          const taskIndex = oldTasks.findIndex(t => t.id === state.draggedTask.id);
          if (taskIndex !== -1) {
            oldTasks.splice(taskIndex, 1);
          }
        }
        
        state.draggedTask.day = newDay;
        if (!state.tasks[newWeekKey]) {
          state.tasks[newWeekKey] = [];
        }
        state.tasks[newWeekKey].push(state.draggedTask);
        
        utils.saveToLocalStorage();
        ui.setCurrentDay(newDay);
        ui.showNotification(`Task moved to ${newDay}`, 'success');
        
        if (elements.calendarModal.classList.contains('active')) {
          calendar.render();
        }
      }
    });
  });

  // Week navigation
  elements.prevWeekBtn.addEventListener('click', () => {
    state.weekOffset--;
    ui.updateWeekLabel('prev');
    ui.updateCurrentDate();
    tasks.render();
    if (elements.calendarModal.classList.contains('active')) {
      calendar.render();
    }
    // Update sidebar weather for new week
    if (weather.lastWeatherData && weather.lastWeatherData.forecast) {
      weather.updateSidebarWeather(weather.lastWeatherData.forecast);
    }
  });

  elements.nextWeekBtn.addEventListener('click', () => {
    state.weekOffset++;
    ui.updateWeekLabel('next');
    ui.updateCurrentDate();
    tasks.render();
    if (elements.calendarModal.classList.contains('active')) {
      calendar.render();
    }
    // Update sidebar weather for new week
    if (weather.lastWeatherData && weather.lastWeatherData.forecast) {
      weather.updateSidebarWeather(weather.lastWeatherData.forecast);
    }
  });

  // Add task buttons
  elements.addTaskBtn.addEventListener('click', () => {
    state.editingTask = null;
    elements.taskForm.reset();
    
    // Check the current day by default
    const dayCheckboxes = document.querySelectorAll('input[name="days"]');
    dayCheckboxes.forEach(checkbox => {
      checkbox.checked = checkbox.value === state.currentDay;
    });
    
    const modalHeader = elements.taskModal.querySelector('.modal-header h2');
    modalHeader.textContent = 'Create Task';
    
    const submitBtn = elements.taskForm.querySelector('button[type="submit"]');
    submitBtn.textContent = 'Create Task';
    
    ui.openModal(elements.taskModal);
  });

  elements.fabAdd.addEventListener('click', () => {
    elements.addTaskBtn.click();
  });

  // Select all days button - toggles between all days and current day only
  document.getElementById('select-all-days')?.addEventListener('click', () => {
    const dayCheckboxes = document.querySelectorAll('input[name="days"]');
    const allChecked = Array.from(dayCheckboxes).every(checkbox => checkbox.checked);
    
    if (allChecked) {
      // If all are checked, deselect all except current day
      dayCheckboxes.forEach(checkbox => {
        checkbox.checked = checkbox.value === state.currentDay;
      });
    } else {
      // Otherwise, select all days
      dayCheckboxes.forEach(checkbox => {
        checkbox.checked = true;
      });
    }
  });

  // Task form submission
  elements.taskForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(elements.taskForm);
    const startTime = formData.get('startTime');
    const endTime = formData.get('endTime');
    
    // Get selected days
    const selectedDays = Array.from(document.querySelectorAll('input[name="days"]:checked'))
      .map(checkbox => checkbox.value);
    
    if (selectedDays.length === 0) {
      ui.showNotification('Please select at least one day', 'warning');
      return;
    }
    
    // Provide helpful feedback for end-time-only tasks
    if (endTime && !startTime) {
      const endTimeInput = document.getElementById('task-end-time');
      const helpText = endTimeInput.parentNode.querySelector('.form-help');
      if (helpText) {
        helpText.style.color = 'var(--primary)';
        helpText.style.fontWeight = '500';
        setTimeout(() => {
          helpText.style.color = 'var(--text-tertiary)';
          helpText.style.fontWeight = 'normal';
        }, 2000);
      }
    }
    
    const taskData = {
      title: formData.get('title'),
      description: formData.get('description'),
      startTime: startTime || '',
      endTime: endTime || '',
      time: '', // Clear the legacy time field to avoid conflicts
      priority: formData.get('priority'),
      color: formData.get('color')
    };
    
    try {
      if (state.editingTask) {
        // When editing, update the task in its original day
        await tasks.update(state.editingTask.id, {
          ...taskData,
          day: state.editingTask.day
        });
        state.editingTask = null;
        ui.showNotification('Task updated', 'success');
      } else {
        // When creating, create task for each selected day
        const createPromises = selectedDays.map(day => 
          tasks.create({
            ...taskData,
            day: day
          })
        );
        
        await Promise.all(createPromises);
        
        if (selectedDays.length > 1) {
          ui.showNotification(`Task created for ${selectedDays.length} days`, 'success');
        } else {
          ui.showNotification('Task created', 'success');
        }
      }
      
      // Update UI
      tasks.render();
      ui.closeModal(elements.taskModal);
      elements.taskForm.reset();
      
      if (elements.calendarModal.classList.contains('active')) {
        calendar.render();
      }
      
    } catch (error) {
      console.error('Error creating/updating task:', error);
      // Don't close modal on error so user can retry
      ui.showNotification('Failed to save task. Please try again.', 'error');
      return;
    }
  });

  // Modal close buttons
  document.querySelectorAll('.modal-close, .modal-cancel, .close-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const modal = e.target.closest('.modal');
      ui.closeModal(modal);
    });
  });

  // Close modal on overlay click
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      const modal = e.target.closest('.modal');
      ui.closeModal(modal);
    });
  });

  // Clear completed tasks
  elements.clearCompletedBtn.addEventListener('click', async () => {
    const confirmed = await ui.showConfirmation({
      title: 'Clear Completed Tasks',
      message: 'Are you sure you want to clear all completed tasks? This action cannot be undone.',
      confirmText: 'Clear All',
      cancelText: 'Cancel',
      type: 'warning'
    });
    
    if (confirmed) {
      tasks.clearCompleted();
      tasks.render();
    }
  });

  // Calendar functionality
  elements.calendarBtn.addEventListener('click', () => {
    calendar.render();
    ui.openModal(elements.calendarModal);
  });

  // Calendar navigation
  document.getElementById('calendar-prev').addEventListener('click', () => {
    state.weekOffset--;
    calendar.render();
    ui.updateWeekLabel('prev');
    // Update sidebar weather for new week
    setTimeout(() => {
      if (weather.lastWeatherData && weather.lastWeatherData.forecast) {
        weather.updateSidebarWeather(weather.lastWeatherData.forecast);
      }
    }, 100);
  });

  document.getElementById('calendar-next').addEventListener('click', () => {
    state.weekOffset++;
    calendar.render();
    ui.updateWeekLabel('next');
    // Update sidebar weather for new week
    setTimeout(() => {
      if (weather.lastWeatherData && weather.lastWeatherData.forecast) {
        weather.updateSidebarWeather(weather.lastWeatherData.forecast);
      }
    }, 100);
  });

  // Theme toggle
  elements.themeToggle.addEventListener('click', async () => {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    await utils.saveTheme(newTheme);
    utils.saveToLocalStorage();
  });

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal.active').forEach(modal => {
        ui.closeModal(modal);
      });
    }
    
    if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
      e.preventDefault();
      elements.addTaskBtn.click();
    }
    
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      elements.calendarBtn.click();
    }
  });

  // ===== Custom Reminder Time Event Handlers =====
  
  // Add reminder button
  const addReminderBtn = document.getElementById('add-reminder-btn');
  if (addReminderBtn) {
    addReminderBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      notifications.toggleAddReminderMenu();
    });
  }

  // Quick reminder options
  const quickReminderButtons = document.querySelectorAll('.quick-reminder-btn');
  quickReminderButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const minutes = parseInt(btn.dataset.minutes);
      notifications.addQuickReminderTime(minutes);
    });
  });

  // Custom reminder form
  const addCustomReminderBtn = document.getElementById('add-custom-reminder-btn');
  if (addCustomReminderBtn) {
    addCustomReminderBtn.addEventListener('click', () => {
      notifications.addCustomReminderTime();
    });
  }

  // Daily summary time input
  const dailySummaryTime = document.getElementById('daily-summary-time');
  if (dailySummaryTime) {
    dailySummaryTime.addEventListener('change', () => {
      notifications.updateDailySummaryTime();
    });
  }

  // Close add reminder menu when clicking outside
  document.addEventListener('click', (e) => {
    const menu = document.querySelector('.add-reminder-menu');
    const btn = document.getElementById('add-reminder-btn');
    
    if (menu && menu.classList.contains('active') && 
        !menu.contains(e.target) && 
        e.target !== btn && 
        !btn.contains(e.target)) {
      menu.classList.remove('active');
    }
  });
};

// ===== Initialize App =====
const init = async () => {
  // Load theme immediately (before Firebase to avoid flash)
  utils.loadTheme();
  
  // Try to load from Firebase first (primary storage)
  const firebaseLoaded = await utils.loadTasksFromFirebase();
  
  if (!firebaseLoaded) {
    // Fallback to local storage if Firebase is not available
    console.log('💾 Using local storage as fallback');
    utils.loadFromLocalStorage();
  }
  
  ui.updateWeekLabel();
  ui.updateCurrentDate();
  ui.setCurrentDay(state.currentDay);
  
  // Initialize weather button with default state
  weather.showDefaultWeatherButton();
  
  // Initialize notifications settings
  notifications.loadSettings();
  
  // Initialize notification scheduler
  if (state.userSettings.notifications_enabled) {
    await notificationScheduler.init();
  }
  
  // Initialize assistant
  assistant.init();
  
  // Initialize class schedule
  await classSchedule.init();
  
  initEventHandlers();

  // quick pattern check on startup (don't show too aggressively)
  setTimeout(() => { try { pattern.showSuggestionsIfAny(2, 2); } catch (e) {} }, 800);
  
  // Run auto-delete on startup
  setTimeout(() => { try { tasks.deleteOldTasks(); } catch (e) {} }, 1000);
  
  // Loader will be hidden after weather initialization completes
  
  setInterval(() => {
    utils.saveToLocalStorage();
  }, 30000);
  
  // Periodic Firebase sync every 5 minutes
  setInterval(() => {
    try { utils.syncWithFirebase(); } catch (e) { console.error('Sync error:', e); }
  }, 300000); // 5 minutes
  
  // Run auto-delete every hour
  setInterval(() => {
    try { tasks.deleteOldTasks(); } catch (e) {}
  }, 3600000); // 1 hour
  
  // Initialize weather - auto-load weather data and hide loader after completion
  const initializeWeatherAndHideLoader = async () => {
    console.log('Starting weather initialization...');
    let weatherCompleted = false;
    
    if ('geolocation' in navigator) {
      console.log('Geolocation is available');
      
      // Try to load weather data in multiple ways
      const tryLoadWeather = async () => {
        try {
          // First, check if we have stored permission and location
          if (weather.checkStoredPermission()) {
            console.log('Weather permission already granted');
            // Always try to load weather data, regardless of shouldRefresh
            await weather.loadWeatherDataSilently();
            // Update weather button for current selected day after loading
            if (weather.lastWeatherData) {
              weather.updateButtonForSelectedDay(state.currentDay);
            }
            weatherCompleted = true;
          } else {
            // Try to load from cached data if available
            const cachedWeather = localStorage.getItem('weather_last_data');
            if (cachedWeather) {
              try {
                const weatherData = JSON.parse(cachedWeather);
                console.log('Loading weather from cache');
                weather.displayWeatherData(weatherData);
                weatherCompleted = true;
              } catch (e) {
                console.log('Error parsing cached weather data:', e);
              }
            }
            
            // For first-time users or users without permission
            if (!weather.hasInteractedWithWeather()) {
              console.log('First time user - opening weather modal automatically');
              weatherCompleted = true; // Consider it complete for loader purposes
              setTimeout(() => {
                weather.showModal();
              }, 1500);
            } else {
              console.log('User has interacted with weather before but no permission - waiting for manual interaction');
              weatherCompleted = true; // Consider it complete for loader purposes
            }
          }
        } catch (error) {
          console.error('Weather initialization error:', error);
          // Try to load from cache as fallback
          const cachedWeather = localStorage.getItem('weather_last_data');
          if (cachedWeather) {
            try {
              const weatherData = JSON.parse(cachedWeather);
              console.log('Fallback: Loading weather from cache after error');
              weather.displayWeatherData(weatherData);
              weatherCompleted = true;
            } catch (e) {
              console.log('Fallback cache loading also failed:', e);
              weatherCompleted = true; // Still mark as complete to avoid hanging
            }
          } else {
            weatherCompleted = true; // Mark as complete even if no cache available
          }
        }
      };
      
      await tryLoadWeather();
    } else {
      console.log('Geolocation not available');
      weatherCompleted = true;
    }
    
    // Hide loader and show app with fade-in animation after weather loading is complete
    console.log('Weather initialization completed, hiding loader and showing app');
    setTimeout(() => {
      // Add loaded class to trigger app fade-in animation
      document.querySelector('.app').classList.add('loaded');
      // Hide loader with a slight delay to allow app animation to start
      setTimeout(() => {
        elements.loader.classList.add('hidden');
      }, 100);
    }, 200); // Small delay to ensure smooth transition
  };
  
  // Start weather initialization with a delay
  setTimeout(initializeWeatherAndHideLoader, 1000);
  
  console.log('Daily Planner initialized');
};

// ===== Class Schedule Management =====
const classSchedule = {
  // Initialize default data structure
  data: {
    semester: {
      name: '',
      startDate: '',
      endDate: ''
    },
    breaks: [],
    classes: []
  },

  async init() {
    await this.loadFromStorage();
    this.bindEvents();
    this.renderAll();
  },

  bindEvents() {
    // Tab switching
    document.querySelectorAll('.settings-tab-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const targetTab = e.target.closest('.settings-tab-btn').dataset.tab;
        this.switchTab(targetTab);
      });
    });

    // Semester form changes
    const semesterInputs = ['semester-name', 'semester-start', 'semester-end'];
    semesterInputs.forEach(id => {
      const input = document.getElementById(id);
      if (input) {
        input.addEventListener('change', async () => await this.updateSemesterInfo());
      }
    });

    // Add break button
    const addBreakBtn = document.getElementById('add-break-btn');
    if (addBreakBtn) {
      addBreakBtn.addEventListener('click', () => this.showAddBreakModal());
    }

    // Add class button
    const addClassBtn = document.getElementById('add-class-btn');
    if (addClassBtn) {
      addClassBtn.addEventListener('click', () => this.showAddClassModal());
    }

    // Save break button
    const saveBreakBtn = document.getElementById('save-break-btn');
    if (saveBreakBtn) {
      saveBreakBtn.addEventListener('click', async () => await this.saveBreak());
    }

    // Save class button
    const saveClassBtn = document.getElementById('save-class-btn');
    if (saveClassBtn) {
      saveClassBtn.addEventListener('click', async () => await this.saveClass());
    }

    // Update class button (for edit modal)
    const updateClassBtn = document.getElementById('update-class-btn');
    if (updateClassBtn) {
      updateClassBtn.addEventListener('click', async () => await this.updateClass());
    }

    // Generate schedule button
    const generateBtn = document.getElementById('generate-schedule-btn');
    if (generateBtn) {
      generateBtn.addEventListener('click', () => this.generateSchedule());
    }

    // Clear schedule button
    const clearBtn = document.getElementById('clear-schedule-btn');
    if (clearBtn) {
      clearBtn.addEventListener('click', () => this.clearGeneratedSchedule());
    }
  },

  switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.settings-tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // Update tab content
    document.querySelectorAll('.settings-tab-content').forEach(content => {
      content.classList.toggle('active', content.id === `${tabName}-tab`);
    });
  },

  async updateSemesterInfo() {
    const nameInput = document.getElementById('semester-name');
    const startInput = document.getElementById('semester-start');
    const endInput = document.getElementById('semester-end');

    if (nameInput && startInput && endInput) {
      this.data.semester = {
        name: nameInput.value,
        startDate: startInput.value,
        endDate: endInput.value
      };
      await this.saveToStorage();
    }
  },

  showAddBreakModal() {
    const modal = document.getElementById('add-break-modal');
    if (modal) {
      // Clear form
      document.getElementById('add-break-form').reset();
      ui.openModal(modal);
    }
  },

  showAddClassModal() {
    const modal = document.getElementById('add-class-modal');
    if (modal) {
      // Clear form
      document.getElementById('add-class-form').reset();
      ui.openModal(modal);
    }
  },

  editClass(classId) {
    const classToEdit = this.data.classes.find(c => c.id === classId);
    if (!classToEdit) {
      ui.showNotification('Class not found', 'error');
      return;
    }

    // Store the ID of the class being edited
    this.editingClassId = classId;
    this.showEditClassModal(classToEdit);
  },

  showEditClassModal(classData) {
    const modal = document.getElementById('edit-class-modal');
    if (modal) {
      // Populate form with existing data
      document.getElementById('edit-class-name').value = classData.name || '';
      document.getElementById('edit-class-code').value = classData.code || '';
      document.getElementById('edit-class-credits').value = classData.credits || '';
      document.getElementById('edit-class-professor').value = classData.professor || '';
      document.getElementById('edit-class-location').value = classData.location || '';
      document.getElementById('edit-class-start-time').value = classData.startTime || '';
      document.getElementById('edit-class-end-time').value = classData.endTime || '';
      document.getElementById('edit-class-color').value = classData.color || '#4A90E2';

      // Set selected days
      const dayCheckboxes = document.querySelectorAll('input[name="edit-class-days"]');
      dayCheckboxes.forEach(checkbox => {
        checkbox.checked = classData.days && classData.days.includes(checkbox.value);
      });

      ui.openModal(modal);
    }
  },

  async saveBreak() {
    const form = document.getElementById('add-break-form');
    const formData = new FormData(form);
    
    const breakData = {
      id: utils.generateId(),
      name: formData.get('break-name') || document.getElementById('break-name').value,
      startDate: formData.get('break-start') || document.getElementById('break-start').value,
      endDate: formData.get('break-end') || document.getElementById('break-end').value
    };

    // Validate
    if (!breakData.name || !breakData.startDate || !breakData.endDate) {
      ui.showNotification('Please fill in all required fields', 'error');
      return;
    }

    if (new Date(breakData.startDate) > new Date(breakData.endDate)) {
      ui.showNotification('Start date must be before end date', 'error');
      return;
    }

    this.data.breaks.push(breakData);
    await this.saveToStorage();
    this.renderBreaks();
    
    const modal = document.getElementById('add-break-modal');
    ui.closeModal(modal);
    ui.showNotification('Break period added successfully', 'success');
  },

  async saveClass() {
    const form = document.getElementById('add-class-form');
    
    const classData = {
      id: utils.generateId(),
      name: document.getElementById('class-name').value,
      code: document.getElementById('class-code').value,
      credits: document.getElementById('class-credits').value,
      professor: document.getElementById('class-professor').value,
      location: document.getElementById('class-location').value,
      startTime: document.getElementById('class-start-time').value,
      endTime: document.getElementById('class-end-time').value,
      color: document.getElementById('class-color').value,
      days: []
    };

    // Get selected days
    const dayCheckboxes = document.querySelectorAll('input[name="class-days"]:checked');
    classData.days = Array.from(dayCheckboxes).map(cb => cb.value);

    // Validate
    if (!classData.name || !classData.startTime || !classData.endTime || classData.days.length === 0) {
      ui.showNotification('Please fill in all required fields', 'error');
      return;
    }

    if (classData.startTime >= classData.endTime) {
      ui.showNotification('Start time must be before end time', 'error');
      return;
    }

    this.data.classes.push(classData);
    await this.saveToStorage();
    this.renderClasses();
    
    const modal = document.getElementById('add-class-modal');
    ui.closeModal(modal);
    ui.showNotification('Class added successfully', 'success');
  },

  async updateClass() {
    if (!this.editingClassId) {
      ui.showNotification('No class selected for editing', 'error');
      return;
    }

    const classData = {
      id: this.editingClassId, // Keep the same ID
      name: document.getElementById('edit-class-name').value,
      code: document.getElementById('edit-class-code').value,
      credits: document.getElementById('edit-class-credits').value,
      professor: document.getElementById('edit-class-professor').value,
      location: document.getElementById('edit-class-location').value,
      startTime: document.getElementById('edit-class-start-time').value,
      endTime: document.getElementById('edit-class-end-time').value,
      color: document.getElementById('edit-class-color').value,
      days: []
    };

    // Get selected days
    const dayCheckboxes = document.querySelectorAll('input[name="edit-class-days"]:checked');
    classData.days = Array.from(dayCheckboxes).map(cb => cb.value);

    // Validate
    if (!classData.name || !classData.startTime || !classData.endTime || classData.days.length === 0) {
      ui.showNotification('Please fill in all required fields', 'error');
      return;
    }

    if (classData.startTime >= classData.endTime) {
      ui.showNotification('Start time must be before end time', 'error');
      return;
    }

    // Find and update the class
    const classIndex = this.data.classes.findIndex(c => c.id === this.editingClassId);
    if (classIndex !== -1) {
      this.data.classes[classIndex] = classData;
      await this.saveToStorage();
      this.renderClasses();
      
      const modal = document.getElementById('edit-class-modal');
      ui.closeModal(modal);
      ui.showNotification('Class updated successfully', 'success');
      
      // Clear the editing ID
      this.editingClassId = null;
    } else {
      ui.showNotification('Class not found', 'error');
    }
  },

  async generateSchedule() {
    if (!this.data.semester.startDate || !this.data.semester.endDate) {
      ui.showNotification('Please set semester start and end dates first', 'error');
      return;
    }

    if (this.data.classes.length === 0) {
      ui.showNotification('Please add at least one class first', 'error');
      return;
    }

    const confirmed = await ui.showConfirmation({
      title: 'Generate Class Schedule',
      message: `This will create recurring class tasks from ${this.data.semester.startDate} to ${this.data.semester.endDate}. This may take a moment for long semesters.`,
      confirmText: 'Generate',
      cancelText: 'Cancel',
      type: 'info'
    });

    if (!confirmed) return;

    // Add loading state to button
    const generateBtn = document.getElementById('generate-schedule-btn');
    const originalHTML = generateBtn ? generateBtn.innerHTML : '';
    if (generateBtn) {
      generateBtn.disabled = true;
      generateBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="18" height="18" class="loading-spinner">
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" fill="none" opacity="0.3"/>
          <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="2" fill="none">
            <animateTransform attributeName="transform" attributeType="XML" type="rotate" from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite"/>
          </path>
        </svg>
        Generating...
      `;
    }

    try {
      ui.showNotification('Generating class schedule...', 'info');
      
      const startDate = new Date(this.data.semester.startDate);
      const endDate = new Date(this.data.semester.endDate);
      let generatedCount = 0;

      // Iterate through each day of the semester
      for (let currentDate = new Date(startDate); currentDate <= endDate; currentDate.setDate(currentDate.getDate() + 1)) {
        // Skip if this date is in a break period
        if (this.isDateInBreak(currentDate)) continue;

        const dayName = currentDate.toLocaleDateString('en-US', { weekday: 'long' });

        // Check each class for this day
        this.data.classes.forEach(classInfo => {
          if (classInfo.days.includes(dayName)) {
            // Create task for this class
            const task = {
              id: utils.generateId(),
              title: classInfo.name,
              description: `${classInfo.code ? classInfo.code + ' - ' : ''}${classInfo.professor ? 'Prof. ' + classInfo.professor : ''}${classInfo.location ? ' @ ' + classInfo.location : ''}`,
              time: classInfo.startTime,
              endTime: classInfo.endTime,
              day: dayName,
              priority: 'medium',
              completed: false,
              color: classInfo.color,
              isClassTask: true,
              classId: classInfo.id,
              date: currentDate.toISOString().split('T')[0],
              // Add absolute week information to prevent reorganization on refresh
              absoluteDate: currentDate.toISOString().split('T')[0],
              preserveWeekPosition: true
            };

            // Generate proper week key for this specific date
            const weekStart = new Date(currentDate);
            const dayOfWeek = weekStart.getDay(); // 0=Sunday, 1=Monday, etc.
            weekStart.setDate(weekStart.getDate() - dayOfWeek); // Go back to Sunday
            
            const year = weekStart.getFullYear();
            const month = (weekStart.getMonth() + 1).toString().padStart(2, '0');
            const date = weekStart.getDate().toString().padStart(2, '0');
            const weekKey = `${year}-${month}-${date}-${dayName}`;

            if (!state.tasks[weekKey]) state.tasks[weekKey] = [];
            
            // Check if this exact class task already exists
            const existingTask = state.tasks[weekKey].find(t => 
              t.isClassTask && 
              t.classId === classInfo.id && 
              t.date === task.date
            );

            if (!existingTask) {
              state.tasks[weekKey].push(task);
              generatedCount++;
            }
          }
        });
      }

      // Save to storage and Firebase
      utils.saveToLocalStorage();
      await this.syncToFirebase();

      // Refresh current view
      tasks.render();
      if (elements.calendarModal.classList.contains('active')) {
        calendar.render();
      }

      ui.showNotification(`Generated ${generatedCount} class sessions successfully!`, 'success');
    } catch (error) {
      console.error('Error generating schedule:', error);
      ui.showNotification('Error generating class schedule', 'error');
    } finally {
      // Restore button state
      if (generateBtn) {
        generateBtn.disabled = false;
        generateBtn.innerHTML = originalHTML || `
          <svg viewBox="0 0 24 24" width="18" height="18">
            <path d="M14.828 10.828a4 4 0 0 0-5.656 0 4 4 0 0 0 0 5.656l5.656-5.656z" stroke="currentColor" stroke-width="2" fill="none"/>
            <path d="M9.172 13.172a4 4 0 0 0 5.656 0 4 4 0 0 0 0-5.656l-5.656 5.656z" stroke="currentColor" stroke-width="2" fill="none"/>
            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" fill="none"/>
          </svg>
          Generate Class Schedule
        `;
      }
    }
  },

  async clearGeneratedSchedule() {
    const confirmed = await ui.showConfirmation({
      title: 'Clear Generated Classes',
      message: 'This will remove all auto-generated class tasks from your planner. Manual tasks will not be affected.',
      confirmText: 'Clear All',
      cancelText: 'Cancel',
      type: 'warning'
    });

    if (!confirmed) return;

    // Add loading state to button
    const clearBtn = document.getElementById('clear-schedule-btn');
    const originalHTML = clearBtn ? clearBtn.innerHTML : '';
    if (clearBtn) {
      clearBtn.disabled = true;
      clearBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="18" height="18" class="loading-spinner">
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" fill="none" opacity="0.3"/>
          <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="2" fill="none">
            <animateTransform attributeName="transform" attributeType="XML" type="rotate" from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite"/>
          </path>
        </svg>
        Clearing...
      `;
    }

    try {
      ui.showNotification('Clearing generated classes...', 'info');
      let removedCount = 0;
      const classTasksToDelete = [];

      // Collect all class task IDs for Firebase deletion
      Object.keys(state.tasks).forEach(weekKey => {
        state.tasks[weekKey].forEach(task => {
          if (task.isClassTask && task.id) {
            classTasksToDelete.push(task.id);
            removedCount++;
          }
        });
      });

      console.log(`🗑️ Deleting ${classTasksToDelete.length} class tasks from Firebase...`);
      
      // Delete from Firebase first using bulk delete
      if (classTasksToDelete.length > 0) {
        try {
          await utils.bulkDeleteTasksFromFirebase(classTasksToDelete);
          console.log('✅ Class tasks deleted from Firebase successfully');
        } catch (error) {
          console.error('⚠️ Some class tasks may not have been deleted from Firebase:', error);
          // Continue with local deletion anyway
        }
      }

      // Remove from local storage after Firebase deletion
      Object.keys(state.tasks).forEach(weekKey => {
        const tasksToKeep = state.tasks[weekKey].filter(task => !task.isClassTask);
        state.tasks[weekKey] = tasksToKeep;
      });

      // Save updated local storage
      utils.saveToLocalStorage();

      // Refresh views
      tasks.render();
      if (elements.calendarModal.classList.contains('active')) {
        calendar.render();
      }

      ui.showNotification(`Removed ${removedCount} generated class tasks`, 'success');
    } catch (error) {
      console.error('Error clearing schedule:', error);
      ui.showNotification('Error clearing class schedule', 'error');
    } finally {
      // Restore button state
      if (clearBtn) {
        clearBtn.disabled = false;
        clearBtn.innerHTML = originalHTML || `
          <svg viewBox="0 0 24 24" width="18" height="18">
            <polyline points="3 6 5 6 21 6" stroke="currentColor" stroke-width="2" fill="none"/>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="2" fill="none"/>
            <line x1="10" y1="11" x2="10" y2="17" stroke="currentColor" stroke-width="2"/>
            <line x1="14" y1="11" x2="14" y2="17" stroke="currentColor" stroke-width="2"/>
          </svg>
          Clear Generated Classes
        `;
      }
    }
  },

  isDateInBreak(date) {
    const dateStr = date.toISOString().split('T')[0];
    return this.data.breaks.some(breakPeriod => {
      return dateStr >= breakPeriod.startDate && dateStr <= breakPeriod.endDate;
    });
  },

  async syncToFirebase() {
    console.log('Syncing class tasks to Firebase...');
    
    try {
      let syncedCount = 0;
      
      // Find all class tasks in state.tasks
      for (const weekKey in state.tasks) {
        const weekTasks = state.tasks[weekKey];
        for (const task of weekTasks) {
          if (task.isClassTask) {
            try {
              await utils.makeApiCall('/api/tasks', 'POST', task);
              syncedCount++;
            } catch (error) {
              console.error(`Failed to sync class task ${task.title}:`, error);
            }
          }
        }
      }
      
      console.log(`✅ Synced ${syncedCount} class tasks to Firebase`);
    } catch (error) {
      console.error('❌ Error syncing class tasks to Firebase:', error);
    }
  },

  renderAll() {
    this.renderSemesterInfo();
    this.renderBreaks();
    this.renderClasses();
  },

  renderSemesterInfo() {
    const nameInput = document.getElementById('semester-name');
    const startInput = document.getElementById('semester-start');
    const endInput = document.getElementById('semester-end');

    if (nameInput) nameInput.value = this.data.semester.name;
    if (startInput) startInput.value = this.data.semester.startDate;
    if (endInput) endInput.value = this.data.semester.endDate;
  },

  renderBreaks() {
    const container = document.getElementById('break-periods-list');
    if (!container) return;

    container.innerHTML = '';

    this.data.breaks.forEach(breakPeriod => {
      const breakEl = document.createElement('div');
      breakEl.className = 'break-item';
      breakEl.innerHTML = `
        <div class="item-header">
          <div>
            <h4 class="item-title">${breakPeriod.name}</h4>
            <p class="item-subtitle">${this.formatDateRange(breakPeriod.startDate, breakPeriod.endDate)}</p>
          </div>
          <div class="item-actions">
            <button class="item-action-btn delete" onclick="classSchedule.deleteBreak('${breakPeriod.id}')">
              <svg viewBox="0 0 24 24" width="14" height="14">
                <polyline points="3 6 5 6 21 6" stroke="currentColor" stroke-width="2" fill="none"/>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="2" fill="none"/>
              </svg>
            </button>
          </div>
        </div>
      `;
      container.appendChild(breakEl);
    });
  },

  renderClasses() {
    const container = document.getElementById('classes-list');
    if (!container) return;

    container.innerHTML = '';

    this.data.classes.forEach(classInfo => {
      const classEl = document.createElement('div');
      classEl.className = 'class-item';
      classEl.style.borderLeftColor = classInfo.color;
      
      const daysHtml = classInfo.days.map(day => 
        `<span class="class-day-tag">${day.substring(0, 3)}</span>`
      ).join('');

      classEl.innerHTML = `
        <div class="item-header">
          <div>
            <h4 class="item-title">${classInfo.name}</h4>
            <p class="item-subtitle">${classInfo.code || 'No course code'}</p>
          </div>
          <div class="item-actions">
            <button class="item-action-btn edit" onclick="classSchedule.editClass('${classInfo.id}')" title="Edit Class">
              <svg viewBox="0 0 24 24" width="14" height="14">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" stroke="currentColor" stroke-width="2" fill="none"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" stroke="currentColor" stroke-width="2" fill="none"/>
              </svg>
            </button>
            <button class="item-action-btn delete" onclick="classSchedule.deleteClass('${classInfo.id}')" title="Delete Class">
              <svg viewBox="0 0 24 24" width="14" height="14">
                <polyline points="3 6 5 6 21 6" stroke="currentColor" stroke-width="2" fill="none"/>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="2" fill="none"/>
              </svg>
            </button>
          </div>
        </div>
        <div class="class-days">${daysHtml}</div>
        <div class="item-details">
          <div class="item-detail">
            <span class="item-detail-label">Time</span>
            <span class="item-detail-value">${utils.formatTime(classInfo.startTime)} - ${utils.formatTime(classInfo.endTime)}</span>
          </div>
          ${classInfo.professor ? `
            <div class="item-detail">
              <span class="item-detail-label">Professor</span>
              <span class="item-detail-value">${classInfo.professor}</span>
            </div>
          ` : ''}
          ${classInfo.location ? `
            <div class="item-detail">
              <span class="item-detail-label">Location</span>
              <span class="item-detail-value">${classInfo.location}</span>
            </div>
          ` : ''}
          ${classInfo.credits ? `
            <div class="item-detail">
              <span class="item-detail-label">Credits</span>
              <span class="item-detail-value">${classInfo.credits}</span>
            </div>
          ` : ''}
        </div>
      `;
      container.appendChild(classEl);
    });
  },

  async deleteBreak(breakId) {
    this.data.breaks = this.data.breaks.filter(b => b.id !== breakId);
    await this.saveToStorage();
    this.renderBreaks();
    ui.showNotification('Break period deleted', 'success');
  },

  async deleteClass(classId) {
    this.data.classes = this.data.classes.filter(c => c.id !== classId);
    await this.saveToStorage();
    this.renderClasses();
    ui.showNotification('Class deleted', 'success');
  },

  formatDateRange(startDate, endDate) {
    const start = new Date(startDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const end = new Date(endDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    return `${start} - ${end}`;
  },

  async saveToStorage() {
    // Save to localStorage as backup
    localStorage.setItem('classScheduleData', JSON.stringify(this.data));
    
    // Save to Firebase as primary storage
    try {
      console.log('💾 Saving class schedule to Firebase...');
      await utils.makeApiCall('/api/class-schedule', 'POST', this.data);
      console.log('✅ Class schedule saved to Firebase successfully');
    } catch (error) {
      console.error('⚠️ Failed to save class schedule to Firebase:', error);
      // Continue with localStorage backup
    }
  },

  async loadFromStorage() {
    try {
      // Try to load from Firebase first (primary storage)
      console.log('📥 Loading class schedule from Firebase...');
      const firebaseData = await utils.makeApiCall('/api/class-schedule', 'GET');
      
      if (firebaseData && (firebaseData.classes || firebaseData.semester || firebaseData.breaks)) {
        this.data = {
          semester: firebaseData.semester || { name: '', startDate: '', endDate: '' },
          breaks: firebaseData.breaks || [],
          classes: firebaseData.classes || []
        };
        console.log('✅ Class schedule loaded from Firebase successfully');
        
        // Backup to localStorage
        localStorage.setItem('classScheduleData', JSON.stringify(this.data));
        return;
      }
    } catch (error) {
      console.log('⚠️ Firebase not available, falling back to localStorage:', error);
    }
    
    // Fallback to localStorage
    const saved = localStorage.getItem('classScheduleData');
    if (saved) {
      try {
        this.data = JSON.parse(saved);
        console.log('📥 Class schedule loaded from localStorage');
      } catch (error) {
        console.error('Error loading class schedule data from localStorage:', error);
      }
    }
  },
};

// Start the app
document.addEventListener('DOMContentLoaded', init);