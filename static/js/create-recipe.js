/**
 * Recipe Creation Form - Client-side Handler
 * Handles form submission via fetch() to /api/recipes endpoint
 */

(function() {
  'use strict';

  const form = document.getElementById('recipeForm');
  const submitBtn = document.getElementById('submitBtn');
  const btnText = submitBtn.querySelector('.btn-text');
  const btnLoader = submitBtn.querySelector('.btn-loader');
  const formMessage = document.getElementById('formMessage');

  /**
   * Display message to user
   */
  function showMessage(message, type = 'error') {
    formMessage.textContent = message;
    formMessage.className = `form-message form-message-${type}`;
    formMessage.style.display = 'block';
    
    // Auto-hide success messages after 3 seconds
    if (type === 'success') {
      setTimeout(() => {
        formMessage.style.display = 'none';
      }, 3000);
    }
  }

  /**
   * Toggle loading state
   */
  function setLoading(isLoading) {
    submitBtn.disabled = isLoading;
    
    if (isLoading) {
      btnText.style.display = 'none';
      btnLoader.style.display = 'inline';
      submitBtn.classList.add('loading');
    } else {
      btnText.style.display = 'inline';
      btnLoader.style.display = 'none';
      submitBtn.classList.remove('loading');
    }
  }

  /**
   * Handle form submission
   */
  async function handleSubmit(event) {
    event.preventDefault();
    
    // Hide any previous messages
    formMessage.style.display = 'none';
    
    // Get form data
    const title = document.getElementById('title').value.trim();
    const content = document.getElementById('content').value.trim();
    
    // Client-side validation
    if (!title) {
      showMessage('Please enter a recipe title', 'error');
      return;
    }
    
    if (title.length > 200) {
      showMessage('Title must be 200 characters or less', 'error');
      return;
    }
    
    if (!content) {
      showMessage('Please enter recipe instructions', 'error');
      return;
    }
    
    // Prepare request
    setLoading(true);
    
    try {
      const response = await fetch('/api/recipes', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'same-origin', // Include session cookie
        body: JSON.stringify({
          title: title,
          content: content
        })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        // Handle error responses
        const errorMsg = data.error || `Server error: ${response.status}`;
        throw new Error(errorMsg);
      }
      
      // Success! Show message and redirect
      showMessage('Recipe created successfully! Redirecting...', 'success');
      
      // Redirect to recipe detail page after short delay
      setTimeout(() => {
        const recipeUrl = `/recipes/${data.id}-${data.slug}`;
        window.location.href = recipeUrl;
      }, 1500);
      
    } catch (error) {
      console.error('Error creating recipe:', error);
      
      // Handle specific error cases
      if (error.message.includes('401') || error.message.includes('Unauthorized')) {
        showMessage('You must be logged in to create a recipe. Redirecting to login...', 'error');
        setTimeout(() => {
          window.location.href = '/login';
        }, 2000);
      } else {
        showMessage(error.message || 'Failed to create recipe. Please try again.', 'error');
      }
      
      setLoading(false);
    }
  }

  /**
   * Character counter for title (optional enhancement)
   */
  const titleInput = document.getElementById('title');
  titleInput.addEventListener('input', function() {
    const remaining = 200 - this.value.length;
    const hint = this.parentElement.querySelector('.form-hint');
    
    if (remaining < 50) {
      hint.textContent = `${remaining} characters remaining`;
      hint.style.color = remaining < 20 ? 'var(--color-text-alt)' : 'var(--color-muted-text)';
    } else {
      hint.textContent = 'A descriptive title for your recipe (max 200 characters)';
      hint.style.color = 'var(--color-muted-text)';
    }
  });

  // Attach form submit handler
  form.addEventListener('submit', handleSubmit);
  
  // Prevent accidental navigation
  let formDirty = false;
  
  form.addEventListener('input', () => {
    formDirty = true;
  });
  
  window.addEventListener('beforeunload', (e) => {
    if (formDirty && !submitBtn.disabled) {
      e.preventDefault();
      e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
      return e.returnValue;
    }
  });

})();
