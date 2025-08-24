(function (global, factory) {
  typeof exports === 'object' && typeof module !== 'undefined' ? factory(exports) :
  typeof define === 'function' && define.amd ? define(['exports'], factory) :
  (global = global || self, factory(global.BpmnComments = {}));
}(this, (function (exports) { 'use strict';

  var COMMENT_HTML =
    '<div class="comment">' +
      '<div data-text></div><a href class="delete icon-delete" data-delete></a>' +
    '</div>';

  function Comments(eventBus, overlays, bpmnjs, translate) {
    function toggleCollapse(element) {
      var o = overlays.get({ element: element, type: 'comments' })[0];
      var overlay = o && o.html;

      if (overlay) {
        var expanded = overlay.classList.contains('expanded');
        eventBus.fire('comments.toggle', { element: element, active: !expanded });

        if (expanded) {
          overlay.classList.remove('expanded');
        } else {
          overlay.classList.add('expanded');
          var textarea = overlay.querySelector('textarea');
          if (textarea) {
            textarea.focus();
          }
        }
      }
    }

    function createCommentBox(element) {
      var overlay = createElementFromHTML(getOverlayHtml(translate));

      var toggleBtn = overlay.querySelector('.toggle');
      if (toggleBtn) {
        toggleBtn.addEventListener('click', function(e) {
          toggleCollapse(element);
        });
      }

      var commentCountEl = overlay.querySelector('[data-comment-count]');
      var textarea = overlay.querySelector('textarea');
      var commentsContainer = overlay.querySelector('.comments');

      function renderComments() {
        commentsContainer.innerHTML = '';
        var comments = getComments(element);

        comments.forEach(function(val) {
          var commentEl = createElementFromHTML(COMMENT_HTML);

          var textEl = commentEl.querySelector('[data-text]');
          if (textEl) {
            textEl.textContent = val[1];
          }

          var deleteBtn = commentEl.querySelector('[data-delete]');
          if (deleteBtn) {
            deleteBtn.addEventListener('click', function(e) {
              e.preventDefault();
              removeComment(element, val);
              renderComments();
              if (textarea) {
                textarea.value = val[1];
              }
            });
          }

          commentsContainer.appendChild(commentEl);
        });

        if (comments.length) {
          overlay.classList.add('with-comments');
        } else {
          overlay.classList.remove('with-comments');
        }

        if (commentCountEl) {
          commentCountEl.textContent = comments.length ? ('(' + comments.length + ')') : '';
        }

        eventBus.fire('comments.updated', { comments: comments });
      }

      if (textarea) {
        textarea.addEventListener('keydown', function(e) {
          if (e.which === 13 && !e.shiftKey) {
            e.preventDefault();
            var comment = textarea.value;

            if (comment) {
              addComment(element, '', comment);
              textarea.value = '';
              renderComments();
            }
          }
        });
      }

      overlays.add(element, 'comments', {
        position: {
          bottom: 10,
          right: 10
        },
        html: overlay
      });

      renderComments();
    }

    eventBus.on('shape.added', function(event) {
      var element = event.element;

      if (element.labelTarget ||
         !element.businessObject.$instanceOf('bpmn:FlowNode')) {
        return;
      }

      defer(function() {
        createCommentBox(element);
      });
    });

    this.collapseAll = function() {
      overlays.get({ type: 'comments' }).forEach(function(c) {
        var html = c.html;
        if (html.classList.contains('expanded')) {
          toggleCollapse(c.element);
        }
      });
    };
  }

  Comments.$inject = ['eventBus', 'overlays', 'bpmnjs', 'translate'];

  // Helper functions
  function defer(fn) {
    setTimeout(fn, 0);
  }

  function createElementFromHTML(htmlString) {
    var div = document.createElement('div');
    div.innerHTML = htmlString.trim();
    return div.firstChild;
  }

  function getOverlayHtml(translate) {
    return '<div class="comments-overlay">' +
      '<div class="toggle">' +
        '<span class="icon-comment"></span>' +
        '<span class="comment-count" data-comment-count></span>' +
      '</div>' +
      '<div class="content">' +
        '<div class="comments"></div>' +
        '<div class="edit">' +
          '<textarea tabindex="1" placeholder="' + (translate ? translate('Add a comment') : 'Add a comment') + '"></textarea>' +
        '</div>' +
      '</div>' +
    '</div>';
  }

  function _getCommentsElement(element, create) {
    var bo = element.businessObject;
    var docs = bo.get('documentation');
    var comments;

    docs.some(function(d) {
      return d.textFormat === 'text/x-comments' && (comments = d);
    });

    if (!comments && create) {
      comments = bo.$model.create('bpmn:Documentation', { textFormat: 'text/x-comments' });
      docs.push(comments);
    }

    return comments;
  }

  function getComments(element) {
    var doc = _getCommentsElement(element);

    if (!doc || !doc.text) {
      return [];
    } else {
      return doc.text.split(/;\r?\n;/).map(function(str) {
        return str.split(/:/, 2);
      });
    }
  }

  function setComments(element, comments) {
    var doc = _getCommentsElement(element, true);

    var str = comments.map(function(c) {
      return c.join(':');
    }).join(';\n;');

    doc.text = str;
  }

  function addComment(element, author, str) {
    var comments = getComments(element);
    comments.push([author, str]);
    setComments(element, comments);
  }

  function removeComment(element, comment) {
    var comments = getComments(element);
    var idx = -1;

    comments.some(function(c, i) {
      var matches = c[0] === comment[0] && c[1] === comment[1];
      if (matches) {
        idx = i;
      }
      return matches;
    });

    if (idx !== -1) {
      comments.splice(idx, 1);
    }

    setComments(element, comments);
  }

  // Auto-inject CSS styles
  function injectStyles() {
    if (document.getElementById('bpmn-comments-styles')) {
      return; // Already injected
    }

    var css = `
      .comments-overlay {
        position: relative;
        z-index: 1000;
        font-family: Arial, sans-serif;
        font-size: 12px;
      }

      .comments-overlay .toggle {
        padding: 4px 6px;
        cursor: pointer;
        display: flex;
        align-items: center;
        min-width: 20px;
        justify-content: center;
        border-radius: 3px;
      }
      
      .comments-overlay.expanded .toggle {
        background: #f5f5f5;        
        border: 1px solid #ccc;        
        box-shadow: 0 1px 3px rgba(0,0,0,0.2);
      }

      .comments-overlay .toggle:hover {
        background: #f5f5f5;
        background: #fff;
        border: 1px solid #ccc;
        box-shadow: 0 1px 3px rgba(0,0,0,0.2);
      }

      .comments-overlay .icon-comment::before {
        content: "💬";
        margin-right: 4px;
      }

      .comments-overlay .comment-count {
        color: #666;
        font-size: 10px;
        margin-left: 2px;
      }

      .comments-overlay .content {
        position: absolute;
        bottom: 100%;
        right: 0;
        width: 250px;
        background: #fff;
        border: 1px solid #ccc;
        border-radius: 3px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        margin-bottom: 5px;
        display: none;
      }

      .comments-overlay.expanded .content {
        display: block;
      }

      .comments-overlay .comments {
        max-height: 200px;
        overflow-y: auto;
        border-bottom: 1px solid #eee;
      }

      .comments-overlay .comment {
        padding: 8px;
        border-bottom: 1px solid #f5f5f5;
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
      }

      .comments-overlay .comment:last-child {
        border-bottom: none;
      }

      .comments-overlay .comment [data-text] {
        flex: 1;
        word-wrap: break-word;
        line-height: 1.4;
      }

      .comments-overlay .comment .delete {
        color: #999;
        text-decoration: none;
        margin-left: 8px;
        cursor: pointer;
      }

      .comments-overlay .comment .delete:hover {
        color: #e74c3c;
      }

      .comments-overlay .comment .delete.icon-delete::before {
        content: "×";
        font-size: 16px;
        font-weight: bold;
      }

      .comments-overlay .edit {
        padding: 8px;
      }

      .comments-overlay textarea {
        width: 100%;
        height: 60px;
        border: 1px solid #ddd;
        border-radius: 3px;
        padding: 6px;
        font-family: Arial, sans-serif;
        font-size: 12px;
        resize: vertical;
        box-sizing: border-box;
      }

      .comments-overlay textarea:focus {
        outline: none;
        border-color: #007bff;
      }

      .comments-overlay.with-comments .toggle {
        background: #e3f2fd;
        border-color: #2196f3;
      }
    `;

    var style = document.createElement('style');
    style.id = 'bpmn-comments-styles';
    style.textContent = css;
    document.head.appendChild(style);
  }

  // Auto-inject styles when the module loads
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', injectStyles);
    } else {
      injectStyles();
    }
  }

  // Module definition for BPMN.js
  var CommentsModule = {
    __init__: ['comments'],
    comments: ['type', Comments]
  };

  // Export for different environments
  exports.default = CommentsModule;
  exports.CommentsModule = CommentsModule;
  exports.Comments = Comments;
  exports.getComments = getComments;
  exports.setComments = setComments;
  exports.addComment = addComment;
  exports.removeComment = removeComment;
  exports._getCommentsElement = _getCommentsElement;
  exports.injectStyles = injectStyles;

  // Global assignment for browser usage
  if (typeof window !== 'undefined') {
    window.BpmnComments = CommentsModule;
    window.BpmnCommentsModule = CommentsModule;
    
    // Also expose utility functions globally
    window.BpmnCommentsUtils = {
      getComments: getComments,
      setComments: setComments,
      addComment: addComment,
      removeComment: removeComment,
      injectStyles: injectStyles
    };
  }

})));