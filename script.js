const addTaskBtn = document.getElementById('add-task-btn');
const taskTitleInput = document.getElementById('task-title-input');
const taskInput = document.getElementById('task-input');
const clockBtn = document.getElementById('clock-btn');
const taskList = document.querySelector('.task-list');
const completedTaskList = document.querySelector('.completed-task-list');
let currentDay = document.getElementById('current-day');
const sidebar = document.querySelector(".sidebar");
const toggleButton = document.getElementById("toggle-sidebar");
const timeInput = document.createElement('input');
timeInput.type = 'time';
timeInput.style.display = 'none';


const tasks = {
    Monday: [],
    Tuesday: [],
    Wednesday: [],
    Thursday: [],
    Friday: [],
    Saturday: [],
    Sunday: []
};

// Check if it's the first time the app is opened
if (!localStorage.getItem('appOpenedBefore')) {
    alert(
        "Patch Notes:\n" +
        "- Added sidebar toggle functionality\n" +
        "- Overall style changes\n" +
        "- Added drag and drop functionality to task elements\n" +
        "- Added the ability to edit tasks"
    );
    localStorage.setItem('appOpenedBefore', 'true'); // Set a flag so the alert doesn't show again
}

const prevWeekBtn = document.getElementById('prev-week-btn');
const nextWeekBtn = document.getElementById('next-week-btn');
const weekLabel = document.getElementById('week-label');
let weekOffset = 0;

toggleButton.addEventListener("click", function () {
    if (sidebar.classList.contains("collapsed")) {
    sidebar.classList.remove("collapsed");
    sidebar.classList.add("expanding");

    setTimeout(() => {
        sidebar.classList.remove("expanding");
    }, 300); // Remove animation class after animation completes
    } else {
    sidebar.classList.add("collapsing");

    setTimeout(() => {
        sidebar.classList.remove("collapsing");
        sidebar.classList.add("collapsed");
    }, 300); // Wait for animation to finish before hiding completely
    }
});

taskTitleInput.addEventListener('keypress', function(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault(); // Prevent default Enter key behavior
        taskInput.focus();
        taskInput.select();
    }
});

taskInput.addEventListener('keypress', function(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault(); // Prevent default Enter key behavior
        addTask();
    }
});

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

function getWeekKey(day) {
    const today = new Date();
    const currentWeekDay = today.getDay();
    const startOfWeek = new Date(today.setDate(today.getDate() - currentWeekDay + 1 + (weekOffset * 7)));
    const weekKey = `${startOfWeek.getFullYear()}-${startOfWeek.getMonth() + 1}-${startOfWeek.getDate()}-${day}`;
    return weekKey;
}

let selectedTime = '';

function formatTimeToAMPM(time) {
    const [hour, minute] = time.split(':');
    let formattedHour = parseInt(hour, 10);
    const ampm = formattedHour >= 12 ? 'PM' : 'AM';
    formattedHour = formattedHour % 12 || 12;
    return `${formattedHour}:${minute} ${ampm}`;
}

function loadTasksFromLocalStorage() {
    const savedTasks = JSON.parse(localStorage.getItem('tasks'));
    if (savedTasks) {
        Object.keys(savedTasks).forEach(day => {
            tasks[day] = savedTasks[day];
        });
    }
    resetWeeklyTasks();
}

function saveTasksToLocalStorage() {
    localStorage.setItem('tasks', JSON.stringify(tasks));
}

function editTask(task, index, day, taskItem) {
    const originalTitle = task.title;
    const originalDescription = task.description;

    const taskTitleInput = document.createElement('input');
    taskTitleInput.type = 'text';
    taskTitleInput.value = task.title;
    taskTitleInput.classList.add('edit-input');

    const taskDescriptionInput = document.createElement('input');
    taskDescriptionInput.type = 'text';
    taskDescriptionInput.value = task.description;
    taskDescriptionInput.classList.add('edit-input');

    const saveBtn = document.createElement('button');
    saveBtn.textContent = 'Save';
    saveBtn.classList.add('save-btn');

    const cancelBtn = document.createElement('button');
    cancelBtn.textContent = 'Cancel';
    cancelBtn.classList.add('cancel-btn');

    saveBtn.addEventListener('click', () => {
        task.title = taskTitleInput.value.trim();
        task.description = taskDescriptionInput.value.trim();
        renderTasks(day);
        saveTasksToLocalStorage();
    });

    cancelBtn.addEventListener('click', () => {
        task.title = originalTitle;
        task.description = originalDescription;
        renderTasks(day);
    });

    taskItem.querySelector('.task-content').innerHTML = '';
    const taskContent = document.createElement('div');
    taskContent.classList.add('task-content');
    taskContent.appendChild(taskTitleInput);
    taskContent.appendChild(document.createTextNode(': '));
    taskContent.appendChild(taskDescriptionInput);
    taskContent.appendChild(saveBtn);
    taskContent.appendChild(cancelBtn);

    taskItem.querySelector('.task-content').appendChild(taskContent);
}

let draggedTask = null;

function createTaskElement(task, index, day) {
    const taskItem = document.createElement('li');
    taskItem.classList.add('task-item');
    taskItem.draggable = true;
    taskItem.dataset.index = index;

    taskItem.addEventListener('dragstart', (e) => {
        draggedTask = {
            task: task,
            index: index,
            day: day,
            weekKey: getWeekKey(day)
        };
        taskItem.classList.add('dragging');
    });

    taskItem.addEventListener('dragend', () => {
        taskItem.classList.remove('dragging');
        draggedTask = null;
    });

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = task.completed;

    const editBtn = document.createElement('button');
    editBtn.textContent = '🖊';
    editBtn.classList.add('edit-btn');

    editBtn.addEventListener('click', () => {
        editTask(task, index, day, taskItem);
    });

    checkbox.addEventListener('change', () => {
        task.completed = checkbox.checked;
        if (task.completed) {
            const completionTime = new Date().toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit'
            });
            task.completedTime = completionTime;
            task.timestamp = '';
            taskDescription.textContent = `${task.description} - Completed at ${completionTime}`;
            taskDescription.classList.add('completed-text');
            completedTaskList.appendChild(taskItem);
            taskItem.classList.add('completed');
            taskItem.appendChild(deleteBtn);

            if (taskItem.contains(editBtn)) {
                taskItem.removeChild(editBtn);
            }
        } else {
            taskDescription.textContent = task.description;
            taskDescription.classList.remove('completed-text');
            taskList.appendChild(taskItem);
            taskItem.classList.remove('completed');

            if (!taskItem.contains(editBtn)) {
                taskItem.appendChild(editBtn);
            }

            if (taskItem.contains(deleteBtn)) {
                taskItem.removeChild(deleteBtn);
            }
        }
        saveTasksToLocalStorage();
    });

    const taskContent = document.createElement('div');
    taskContent.classList.add('task-content');

    const taskTitle = document.createElement('span');
    taskTitle.classList.add('task-title');
    taskTitle.textContent = task.title;

    const taskDescription = document.createElement('span');
    taskDescription.classList.add('task-description');
    taskDescription.textContent = task.timestamp ? `${task.description} - ${task.timestamp}` : task.description;

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
    if (!task.completed) {
        taskItem.appendChild(editBtn);
    }
    if (task.completed) {
        taskItem.appendChild(deleteBtn);
    }

    return taskItem;
}

document.head.insertAdjacentHTML('beforeend', `
  <style>
    .edit-input {
      border: 2px;
      border-color: rgb(42, 66, 61);
      border-radius: 5px;
      padding: 5px;
      outline: none;
      background: rgba(0, 0, 0, 0.1);
      transition: all 0.3s ease-in-out;
    }

    .edit-input:focus {
      background: rgba(0, 0, 0, 0.1);
      box-shadow: 0 0 10px rgba(26, 188, 156, 0.9);
    }

    .save-btn {
      font-family: 'Poppins', sans-serif;
      background-color: rgb(76, 195, 171);
      color: white;
      border: none;
      padding: 5px 10px;
      border-radius: 5px;
      border-color: white;
      border: 2px;
      cursor: pointer;
      transition: background-color 0.3s ease-in-out;
      margin-left: 5px;
    }

    .save-btn:hover {
      background-color: rgb(26, 188, 156);
      transition: all 0.3s ease-in-out;
      transform: scale(1.05 );
    }

    .cancel-btn {
      font-family: 'Poppins', sans-serif;
      background-color:rgb(188, 26, 26);
      color: white;
      border: none;
      padding: 5px 10px;
      border-radius: 5px;
      cursor: pointer;
      transition: background-color 0.3s ease-in-out;
      margin-left: 5px;
    }

    .cancel-btn:hover {
      transition: all 0.3s ease-in-out;
      transform: scale(1.05 );
      background-color: darkred;
    }

    .task-item {
      transition: background-color 0.2s ease;
    }

    .task-item:hover {
      background-color: #f0f0f0;
    }

    .task-item.dragging {
        opacity: 0.5;
        background-color: #ddd;
    }

    .task-list {
      min-height: 50px; /* Ensure the list can receive drops */
    }

    .task-list li {
      cursor: pointer;
    }

    .day-item {
      cursor: pointer;
    }
    .day-item.dragover {
      background-color: #aaf;
    }
  </style>
`);

function renderTasks(day) {
    const weekKey = getWeekKey(day);
    taskList.innerHTML = '';
    completedTaskList.innerHTML = '';

    if (!tasks[weekKey]) {
        tasks[weekKey] = [];
    }

    tasks[weekKey].forEach((task, index) => {
        const taskItem = createTaskElement(task, index, day);
        taskItem.dataset.index = index;

        if (task.completed) {
            completedTaskList.appendChild(taskItem);
        } else {
            taskList.appendChild(taskItem);
        }
    });
}

function addTask() {
    const taskTitle = taskTitleInput.value.trim();
    const taskDescription = taskInput.value.trim();
    const userTime = selectedTime ? formatTimeToAMPM(selectedTime) : '';

    if (taskDescription !== '') {

        const weekKey = getWeekKey(currentDay.textContent);
        const newTask = {
            title: taskTitle,
            description: taskDescription,
            completed: false,
            timestamp: userTime
        };

        if (!tasks[weekKey]) {
            tasks[weekKey] = [];
        }
        tasks[weekKey].push(newTask);
        renderTasks(currentDay.textContent);

        taskTitleInput.value = '';
        taskInput.value = '';
        selectedTime = '';
        saveTasksToLocalStorage();

    } else {
        alert('Please enter a description for the task.');
    }
}

function setCurrentDay(day) {
    currentDay.textContent = day;
    renderTasks(day);
}

function resetWeeklyTasks() {
    const today = new Date();
    const lastResetDate = localStorage.getItem('lastResetDate');
    const isMonday = today.getDay() === 1;

    if (isMonday && lastResetDate !== today.toDateString()) {
        const lastWeekTasks = {};
        const lastWeekStart = new Date(today);
        lastWeekStart.setDate(today.getDate() - 7);
        const lastWeekEnd = new Date(today);
        lastWeekEnd.setDate(today.getDate() - 1);

        for (let d = new Date(lastWeekStart); d <= lastWeekEnd; d.setDate(d.getDate() + 1)) {
            const formattedDate = d.toDateString();
            if (tasks[formattedDate]) {
                tasks[formattedDate] = [];
            }
        }

        saveTasksToLocalStorage();
        localStorage.setItem('lastResetDate', today.toDateString());
        alert('Last week\'s tasks have been reset!');
        renderTasks(currentDay.textContent);
    }
}

clockBtn.addEventListener('click', () => {
    timeInput.type = 'text';

    if (!document.body.contains(timeInput)) {
        taskInput.parentElement.insertBefore(timeInput, addTaskBtn);
    }

    timeInput.style.display = 'inline';
    timeInput.style.marginLeft = '10px';
    timeInput.style.padding = '5px';
    timeInput.style.fontSize = '14px';

    timeInput.placeholder = 'HH:MM';

    setTimeout(() => timeInput.focus(), 100);
});

clockBtn.addEventListener('change', (e) => {
    selectedTime = e.target.value;
    timeInput.style.display = 'none';
});

addTaskBtn.addEventListener('click', addTask);

const dayItems = document.querySelectorAll('.day-item');

//DRAG AND DROP
dayItems.forEach(dayItem => {
    dayItem.addEventListener('dragover', (e) => {
        e.preventDefault();
        dayItem.classList.add('dragover');
    });

    dayItem.addEventListener('dragleave', () => {
        dayItem.classList.remove('dragover');
    });

    dayItem.addEventListener('drop', () => {
        dayItem.classList.remove('dragover');
        if (draggedTask) {
            const newDay = dayItem.textContent;
            const newWeekKey = getWeekKey(newDay);

            // Remove the task from its original day
            const originalTaskArray = tasks[draggedTask.weekKey];
            originalTaskArray.splice(draggedTask.index, 1);

            // Add the task to the new day
            if (!tasks[newWeekKey]) {
                tasks[newWeekKey] = [];
            }
            tasks[newWeekKey].push(draggedTask.task);

            // Save and re-render
            saveTasksToLocalStorage();
            renderTasks(draggedTask.day); // Re-render original day
            setCurrentDay(newDay); //Render new day
            dayItems.forEach(item => item.classList.remove('active'));
            dayItem.classList.add('active');
            draggedTask = null;
        }
    });

    dayItem.addEventListener('click', () => {
        setCurrentDay(dayItem.textContent);
        dayItems.forEach(item => item.classList.remove('active'));
        dayItem.classList.add('active');
    });
});

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

updateButtonVisibility();
