const addTaskBtn = document.getElementById('add-task-btn');  // Get and assign variables to all elements
const taskTitleInput = document.getElementById('task-title-input');  
const taskInput = document.getElementById('task-input');  
const clockBtn = document.getElementById('clock-btn');
const taskList = document.querySelector('.task-list');
const completedTaskList = document.querySelector('.completed-task-list');
let currentDay = document.getElementById('current-day');
const tasks = { // Load separate lists for each day of the week
  Monday: [],
  Tuesday: [],
  Wednesday: [],
  Thursday: [],
  Friday: [],
  Saturday: [],
  Sunday: []
};

// Event Listeners to update the previous and next week buttons. Makes right/left buttons disappear when it goes to last week and two weeks from now.
const prevWeekBtn = document.getElementById('prev-week-btn');
const nextWeekBtn = document.getElementById('next-week-btn');
const weekLabel = document.getElementById('week-label');
let weekOffset = 0;

prevWeekBtn.addEventListener('click', () => {
  if (weekOffset > -1) {
    weekOffset--;
    updateWeekLabel();
    renderTasks(currentDay.textContent);
  }
  updateButtonVisibility();
});

nextWeekBtn.addEventListener('click', () => {
  if (weekOffset < 2) {
    weekOffset++;
    updateWeekLabel();
    renderTasks(currentDay.textContent);
  }
  updateButtonVisibility();
});

//Function to update label of which week it is
function updateWeekLabel() {
  switch (weekOffset) {
    case -1:
      weekLabel.textContent = 'Last Week';
      break;
    case 0:
      weekLabel.textContent = 'This Week';
      break;
    case 1:
      weekLabel.textContent = 'Next Week';
      break;
    case 2:
      weekLabel.textContent = 'Two Weeks from Now';
      break;
    default:
      weekLabel.textContent = `${Math.abs(weekOffset)} Weeks ${weekOffset > 0 ? 'from Now' : 'Ago'}`;
  }
}

function updateButtonVisibility() {
  prevWeekBtn.style.display = weekOffset <= -1 ? 'none' : 'inline-block';
  nextWeekBtn.style.display = weekOffset >= 2 ? 'none' : 'inline-block';
}

//Function to get what week it is and what previous and next weeks are
function getWeekKey(day) {
  const today = new Date();
  const currentWeekDay = today.getDay();
  const startOfWeek = new Date(today.setDate(today.getDate() - currentWeekDay + 1 + (weekOffset * 7)));
  const weekKey = `${startOfWeek.getFullYear()}-${startOfWeek.getMonth() + 1}-${startOfWeek.getDate()}-${day}`;
  return weekKey;
}

let selectedTime = ''; // Initialize selectedTime variable to null

function formatTimeToAMPM(time) { // Convert military time to AM/PM
  const [hour, minute] = time.split(':');
  let formattedHour = parseInt(hour, 10);
  const ampm = formattedHour >= 12 ? 'PM' : 'AM';
  formattedHour = formattedHour % 12 || 12; // Convert 0 to 12
  return `${formattedHour}:${minute} ${ampm}`;
}

function loadTasksFromLocalStorage() { // Load tasks from local storage
  const savedTasks = JSON.parse(localStorage.getItem('tasks'));
  if (savedTasks) {
    Object.keys(savedTasks).forEach(day => {
      tasks[day] = savedTasks[day];
    });
  }
  resetWeeklyTasks();
}

function saveTasksToLocalStorage() { // Save tasks to local storage
  localStorage.setItem('tasks', JSON.stringify(tasks));
}

function createTaskElement(task, index, day) { // Function to create a task element in the task list
  const taskItem = document.createElement('li');
  taskItem.classList.add('task-item');
  taskItem.draggable = true;
  taskItem.dataset.index = index;

  const checkbox = document.createElement('input'); // add checkbox to each individual task element
  checkbox.type = 'checkbox'; 
  checkbox.checked = task.completed;

  checkbox.addEventListener('change', () => {
    task.completed = checkbox.checked;
    if (task.completed) {//Change style of individual task if task is completed
      const completionTime = new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'}); // Get current time
      task.completedTime = completionTime; // Store the completion time
      task.timestamp = ''; // Remove previous timestamp
      taskDescription.textContent = `${task.description} - Completed at ${completionTime}`; // Update task description
      taskDescription.classList.add('completed-text'); // Add class for completed tasks
      document.querySelector('.completed-task-list').appendChild(taskItem);
      taskItem.classList.add('completed');
      taskItem.appendChild(deleteBtn);
    } else {
      taskDescription.textContent = task.description; // Remove completion time from task description
      taskDescription.classList.remove('completed-text'); 
      document.querySelector('.task-list').appendChild(taskItem);
      taskItem.classList.remove('completed');
      if (taskItem.contains(deleteBtn)) {
        taskItem.removeChild(deleteBtn); 
      }
    }
    saveTasksToLocalStorage();
  });

  //Creating and added content for each task 
  const taskContent = document.createElement('div');
  taskContent.classList.add('task-content');

  //Add title to the task
  const taskTitle = document.createElement('span');
  taskTitle.classList.add('task-title');
  taskTitle.textContent = task.title;

  //Add description to the task
  const taskDescription = document.createElement('span');
  taskDescription.classList.add('task-description');
  taskDescription.textContent = task.timestamp ? //Add timestamp if user added a time to task
    `${task.description} - ${task.timestamp}` : 
    task.description;

  taskContent.appendChild(taskTitle);
  taskContent.appendChild(document.createTextNode(': '));
  taskContent.appendChild(taskDescription);

  const deleteBtn = document.createElement('button');
  deleteBtn.textContent = '🗑️';
  deleteBtn.classList.add('delete-btn');

  deleteBtn.addEventListener('click', () => {
    const weekKey = getWeekKey(day);
    const taskArray = tasks[weekKey];
    taskArray.splice(index, 1);
    saveTasksToLocalStorage();
    renderTasks(day);
  });

  taskItem.appendChild(checkbox);
  taskItem.appendChild(taskContent);
  if (task.completed) {
    taskItem.appendChild(deleteBtn); 
  }

  return taskItem;
}

function renderTasks(day) { // Function to render tasks
  const weekKey = getWeekKey(day);
  taskList.innerHTML = '';
  completedTaskList.innerHTML = '';

  if (!tasks[weekKey]) {
    tasks[weekKey] = [];
  }

  tasks[weekKey].forEach((task, index) => {
    const taskItem = createTaskElement(task, index, day);
    if (task.completed) {
      completedTaskList.appendChild(taskItem);
    } else {
      taskList.appendChild(taskItem);
    }
  });
}

function addTask() { // Function to add task to the task list 
  const taskTitle = taskTitleInput.value.trim();
  const taskDescription = taskInput.value.trim();
  const userTime = selectedTime ? formatTimeToAMPM(selectedTime) : '';
  const weekKey = getWeekKey(currentDay.textContent);

  if (taskDescription !== '') {//Make sure that there is a task description 
    const newTask = {
      title: taskTitle !== '' ? taskTitle : 'Untitled Task',
      description: taskDescription,
      completed: false,
      timestamp: userTime
    };

    if (!tasks[weekKey]) {
      tasks[weekKey] = [];
    }

    tasks[weekKey].push(newTask);
    taskTitleInput.value = '';
    taskInput.value = '';
    selectedTime = '';
    renderTasks(currentDay.textContent);
    saveTasksToLocalStorage();
  } else { //If a user tries to enter a task with no description an alert pops up 
    alert('Please enter a description for the task.');
  }
}


// Set the current day
function setCurrentDay(day) {
  currentDay.textContent = day;
  renderTasks(day);
}

function resetWeeklyTasks() {
  const today = new Date();
  const lastResetDate = localStorage.getItem('lastResetDate');
  const isMonday = today.getDay() === 1; // 0 = Sunday, 1 = Monday

  // Check if today is Monday and last reset wasn't today
  if (isMonday && lastResetDate !== today.toDateString()) {
    // Calculate the date range for the last week
    const lastWeekTasks = {};
    const lastWeekStart = new Date(today);
    lastWeekStart.setDate(today.getDate() - 7); // Last Monday
    const lastWeekEnd = new Date(today);
    lastWeekEnd.setDate(today.getDate() - 1); // Last Sunday

    // Loop through the last week's days
    for (let d = new Date(lastWeekStart); d <= lastWeekEnd; d.setDate(d.getDate() + 1)) {
      const formattedDate = d.toDateString(); // Use the date string as the key
      if (tasks[formattedDate]) {
        tasks[formattedDate] = []; // Clear tasks for that day
      }
    }

    // Save updated tasks and update last reset date
    saveTasksToLocalStorage();
    localStorage.setItem('lastResetDate', today.toDateString());
    alert('Last week\'s tasks have been reset!');
    renderTasks(currentDay.textContent);
  }
}


// Event listener for the clock button to allow time selection
clockBtn.addEventListener('click', () => {
  // Ensure the time input only shows when the clock button is clicked
  timeInput.type = 'time';
  timeInput.required = true;
  timeInput.style.display = 'inline';
  timeInput.style.marginLeft = '10px';
  timeInput.style.padding = '5px';
  timeInput.style.fontSize = '14px';

  // Insert the time input just before the Add Task button
  taskInput.parentElement.insertBefore(timeInput, addTaskBtn);
  timeInput.focus();  // Set focus on the time input when it's visible
});

// Event listener for the time input field to store the selected time
clockBtn.addEventListener('change', (e) => {
  selectedTime = e.target.value;  // Store the selected time
  timeInput.style.display = 'none';  // Hide the time input after selection
});

// Event listener for adding a task
addTaskBtn.addEventListener('click', addTask);

// Event listeners for sidebar day selection
const dayItems = document.querySelectorAll('.day-item');
dayItems.forEach(dayItem => {
  dayItem.addEventListener('click', () => {
    setCurrentDay(dayItem.textContent);
    dayItems.forEach(item => item.classList.remove('active'));
    dayItem.classList.add('active');
  });
});

// Load tasks from localStorage and set initial day to Monday
loadTasksFromLocalStorage();
setCurrentDay('Monday');

const style = document.createElement('style');
style.textContent = `
.task-item input[type="checkbox"] {
  cursor: pointer;
  width: 18px;
  border-color:rgb(28, 26, 26);
  height: 18px;
  margin-right: 10px;
  appearance: none;
  border: 2px solid #ccc;
  border-radius: 8px;
  position: relative;
  transition: all 0.2s ease;
}

.task-item input[type="checkbox"]:checked {
  background-color: #1abc9c;
  border-color: #1abc9c;
}

.task-item input[type="checkbox"]:checked::after {
  content: '✓';
  position: absolute;
  color: white;
  font-size: 14px;
  left: 2px;
  top: -2px;
}

.task-item input[type="checkbox"]:hover {
  border-color: #1abc9c;
}
`;
document.head.appendChild(style);

// Initial call to set button visibility
updateButtonVisibility();
