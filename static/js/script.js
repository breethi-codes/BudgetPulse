
function drawCategoryChart() {
    const canvas = document.getElementById('categoryChart');
    if (!canvas) {
        return; 
    }

    if (typeof Chart === 'undefined') {
        console.error('Chart.js did not load. Please check the internet connection.');
        return;
    }

    try {
        
        const labels = JSON.parse(canvas.dataset.labels);
        const totals = JSON.parse(canvas.dataset.totals);

        new Chart(canvas.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: totals,
                    backgroundColor: ['#4f46e5', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { boxWidth: 12 }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Error rendering chart:', error);
    }
}


function setupMonthPicker() {
    const monthForm = document.getElementById('monthForm');
    const monthInput = document.getElementById('month');
    if (!monthForm || !monthInput) {
        return;
    }
    monthInput.addEventListener('change', function () {
        if (monthInput.value !== '') {
            monthForm.submit();
        }
    });
}


function showFormError(form, message) {
    removeFormError(form);
    const box = document.createElement('div');
    box.className = 'alert alert-error js-form-error';
    box.setAttribute('role', 'alert');
    box.textContent = message;
    form.parentNode.insertBefore(box, form);
}

function removeFormError(form) {
    const oldBox = form.parentNode.querySelector('.js-form-error');
    if (oldBox) {
        oldBox.remove();
    }
}

function setupExpenseFormCheck() {
    const form = document.getElementById('expenseForm');
    if (!form) {
        return;
    }
    form.addEventListener('submit', function (event) {
        const title = form.elements['title'].value.trim();
        const amount = parseFloat(form.elements['amount'].value);

        if (title === '') {
            showFormError(form, 'Please enter the expense title.');
            event.preventDefault();
        } else if (isNaN(amount) || amount <= 0) {
            showFormError(form, 'Amount must be greater than zero.');
            event.preventDefault();
        } else {
            removeFormError(form);
        }
    });
}


function setupDeleteConfirm() {
    const deleteForms = document.querySelectorAll('.delete-form');
    deleteForms.forEach(function (form) {
        form.addEventListener('submit', function (event) {
            if (!confirm('Are you sure you want to delete this expense?')) {
                event.preventDefault();
            }
        });
    });
}


function setupDoubleSubmitGuard() {
    document.querySelectorAll('form').forEach(function (form) {
        if (form.method !== 'post') {
            return; 
        }
        form.addEventListener('submit', function (event) {
            if (event.defaultPrevented) {
                return; 
            }
            const button = form.querySelector('button[type="submit"]');
            if (button) {
                button.dataset.originalText = button.textContent;
                button.disabled = true;
                button.textContent = 'Please wait...';
            }
        });
    });
}


window.addEventListener('pageshow', function () {
    document.querySelectorAll('button[data-original-text]').forEach(function (button) {
        button.disabled = false;
        button.textContent = button.dataset.originalText;
    });
});

document.addEventListener('DOMContentLoaded', function () {
    drawCategoryChart();
    setupMonthPicker();
    setupExpenseFormCheck();
    setupDeleteConfirm();
    setupDoubleSubmitGuard();
});