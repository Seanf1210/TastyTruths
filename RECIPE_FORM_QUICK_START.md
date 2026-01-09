# Recipe Creation Flow - Quick Start Guide

## What Was Changed

### 1. New Files Created
- `services/forms.py` - Flask-WTF form with validation
- `templates/recipe_detail.html` - Recipe display page
- `RECIPE_CREATION_IMPLEMENTATION.md` - Detailed documentation
- `migrations/versions/2024_add_rich_recipe_fields.py` - Database migration

### 2. Files Modified
- `services/models.py` - Added new fields to Recipe model
- `templates/create_recipe.html` - Updated form with new fields
- `app.py` - Updated routes, added MAX_CONTENT_LENGTH, imports
- `static/css/styles.css` - Added form and detail page styling

### 3. Database Changes
Run migration to add new columns:
```bash
flask db upgrade
```

This adds:
- `instructions` (Text) - Step-by-step directions
- `ingredients` (Text) - Newline-separated list
- `image_filename` (String, nullable) - Path to uploaded image
- `estimated_cost` (String) - Cost estimate

---

## Form Fields

| Field | Type | Required | Validation |
|-------|------|----------|-----------|
| Title | Text | Yes | 3-150 chars |
| Image | File | No | jpg/png/webp/gif, max 2MB |
| Instructions | Textarea | Yes | Min 10 chars |
| Ingredients | Textarea | Yes | At least 1 line |
| Prep Time | Integer | No | 0 or positive |
| Cook Time | Integer | No | 0 or positive |
| Estimated Cost | Text | No | Max 50 chars |

---

## Route Changes

### Create Recipe Page (GET/POST)
- **URL**: `/recipes/create`
- **Auth**: Login required
- **Method**: GET displays form, POST processes submission
- **On Success**: Redirects to recipe detail page
- **On Error**: Re-renders form with error messages

### Recipe Detail Page (GET)
- **URL**: `/recipes/{id}-{slug}`
- **Auth**: None required (public)
- **Content**: Full recipe with image, timing, ingredients list, instructions

---

## Image Upload Handling

### How It Works
1. User selects an image file from form
2. Server validates: type (jpg/png/webp/gif) and size (<2MB)
3. File renamed with UUID to ensure uniqueness
4. Saved to `static/uploads/recipes/`
5. Relative path stored in database

### Example
- User uploads: `chocolate_chip.jpg`
- Saved as: `static/uploads/recipes/abc123def456_chocolate_chip.jpg`
- DB stores: `uploads/recipes/abc123def456_chocolate_chip.jpg`
- Template displays: `{{ url_for('static', filename=recipe.image_filename) }}`

### No Image Scenario
- Image field is optional
- If empty, `image_filename` is None
- Recipe detail page shows no image section

---

## Form Validation

### Client-Side (WTForms)
- Required field checks
- Length validation
- Number range validation
- File type/size validation

### Error Display
Errors show inline below each field in red:
```html
{% if form.title.errors %}
  <small class="form-error">{{ form.title.errors[0] }}</small>
{% endif %}
```

### Flash Messages
Success/error messages display at top of form after submission:
```html
{% with messages = get_flashed_messages(with_categories=true) %}
  {% for category, message in messages %}
    <div class="alert alert-{{ category }}">{{ message }}</div>
  {% endfor %}
{% endwith %}
```

---

## Recipe Detail Display

### Image
Shows if `image_filename` is not null:
```html
{% if recipe.image_filename %}
  <img src="{{ url_for('static', filename=recipe.image_filename) }}" />
{% endif %}
```

### Ingredients
Splits newline-separated storage into list items:
```
Server (Python): Split by '\n' → pass list to template
Template: Loop and render as <ul><li>
```

### Instructions
Preserves line breaks:
```html
{{ recipe.instructions | replace('\n', '<br>') | safe }}
```

### Timing Info
Shows prep, cook, and total time if available:
- `prep_time_minutes`
- `cook_time_minutes`
- Total = prep + cook (auto-calculated in template)

### Cost
Shows estimated cost if provided:
- No validation on format
- User can enter: "$12", "12.50", "$12-15", etc.

---

## Backward Compatibility

### Old API Endpoint Still Works
- `/api/recipes` (POST with JSON) still creates recipes
- Only sets `title` and `content` fields
- New fields default to null
- Useful for old JavaScript-based submission

### Existing Recipes
- No breaking changes
- New fields are nullable
- Recipe detail page handles missing data gracefully
- Old recipes display without image/timing/cost

---

## Configuration

### File Upload Size Limit
In `app.py`:
```python
MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2MB
```

To change: modify the value and restart Flask.

### Uploads Directory
- Auto-created on first upload
- Must have write permissions
- Path: `static/uploads/recipes/`

---

## Testing Steps

1. **Start Flask app**: `python app.py`
2. **Login** at `/login`
3. **Go to** `/recipes/create`
4. **Fill form**:
   - Title: "Test Recipe"
   - Instructions: "Step 1: do something\nStep 2: do something else"
   - Ingredients: "1 cup flour\n2 eggs\n1 cup sugar"
   - Optionally upload an image
   - Fill timing/cost if desired
5. **Submit** and verify redirect to detail page
6. **Check detail page** displays all fields correctly
7. **Verify error handling** by testing invalid inputs:
   - Leave title empty
   - Upload non-image file
   - Leave ingredients empty

---

## CSS Classes Reference

### Form
- `.recipe-form` - Main form container
- `.form-group` - Field wrapper
- `.form-control` - Input/textarea element
- `.form-control-error` - Error state styling
- `.form-error` - Error message text
- `.form-hint` - Helper text
- `.form-row` - Multi-column layout
- `.form-actions` - Button container

### Recipe Detail
- `.recipe-detail` - Main container
- `.recipe-header` - Title section
- `.recipe-image-container` - Image wrapper
- `.recipe-image` - Image element
- `.recipe-info-section` - Timing/cost grid
- `.info-grid` / `.info-item` - Info layout
- `.recipe-content` - Two-column layout
- `.recipe-ingredients-section` - Left column
- `.recipe-instructions-section` - Right column
- `.ingredients-list` / `.ingredient-item` - List styling
- `.instructions-text` - Formatted text
- `.recipe-actions` - Bottom buttons

---

## Troubleshooting

### Issue: Image not displaying
- Check file was uploaded: `ls static/uploads/recipes/`
- Verify `image_filename` in database
- Check file permissions

### Issue: Ingredients not showing as list
- Verify they're stored with `\n` separator
- Check ingredients weren't stored as empty
- Verify template splitting logic

### Issue: Form validation errors not showing
- Ensure form fields render with `{{ form.field() }}`
- Check `form.validate_on_submit()` is called
- Verify error block condition: `{% if form.field.errors %}`

### Issue: Upload file too large
- Error: "Request Entity Too Large" (413)
- Solution: Reduce file size or change `MAX_CONTENT_LENGTH`
- Max set to 2MB, change in `app.py`

### Issue: Migration fails
- Run: `flask db upgrade`
- Check database isn't locked
- Verify migrations directory exists

---

## Files Summary

| File | Purpose | Status |
|------|---------|--------|
| `services/forms.py` | WTForm validation & rendering | NEW |
| `templates/recipe_detail.html` | Recipe display page | NEW |
| `migrations/versions/2024_*` | Database schema | NEW |
| `services/models.py` | Recipe model fields | MODIFIED |
| `templates/create_recipe.html` | Recipe form | MODIFIED |
| `static/css/styles.css` | Form & detail styling | MODIFIED |
| `app.py` | Routes & config | MODIFIED |

---

## Next Steps

1. **Apply migration**: `flask db upgrade`
2. **Test form submission**: Visit `/recipes/create`
3. **Verify uploads**: Check `/static/uploads/recipes/` after upload
4. **Test detail page**: Create recipe and view result
5. **Check database**: Verify new fields saved correctly
6. **Test error states**: Try invalid inputs, missing files, etc.

---

## Security Notes

✓ CSRF protection: Automatic with Flask-WTF  
✓ File validation: Type and size checks  
✓ Secure filenames: UUID + `secure_filename()`  
✓ SQL injection: SQLAlchemy ORM prevents this  
✓ XSS prevention: Jinja2 auto-escapes by default  
✓ Auth required: Login needed to create recipes  

---

## Performance Notes

- Image uploads capped at 2MB
- Ingredients split at runtime (not indexed)
- No pagination on ingredient display
- Detail page generates single query
- Old API endpoint still available if needed

---

## Future Enhancements

- Image thumbnail generation
- Ingredient quantities/units parsing
- Recipe categories/tags
- Rating/review system
- Nutritional information
- Recipe search/filter
- User recipe history
- Recipe sharing/exporting
