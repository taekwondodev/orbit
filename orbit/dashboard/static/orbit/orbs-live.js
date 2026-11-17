/* global horizon */
// The panel is English only, whatever the user's language.
(function ($) {
  'use strict';

  function elapsed(ms) {
    var seconds = Math.max(0, Math.round(ms / 1000));
    if (seconds < 60) {
      return seconds + ' s';
    }
    return Math.floor(seconds / 60) + ' min';
  }

  function statuses($table) {
    var seen = {};
    $table.find('tbody tr[data-object-id]').each(function () {
      seen[this.getAttribute('data-object-id')] = this.getAttribute('data-orbit-status');
    });
    return seen;
  }

  horizon.addInitFunction(function () {
    $('[data-orbit-live]').each(function () {
      var $root = $(this);
      var $content = $root.find('.orbit-live-content');
      var $status = $root.find('.orbit-live-status');
      var timer;
      var ticker;
      var request;
      var stopped = false;
      var pendingRefresh = false;
      var failed = false;
      var lastUpdate = Date.now();
      var lastMarkup;
      var lastOverview;

      function showAge() {
        var age = elapsed(Date.now() - lastUpdate);
        $status.find('.orbit-live-age').text(
          (failed ? '· data from ' : '· updated ') + age + ' ago');
      }

      function showStatus(message, failure, login) {
        failed = failure;
        $status.toggleClass('orbit-stale', failure);
        var $message = $status.find('.orbit-live-message');
        // The message is a live region: rewriting it would announce it again.
        if ($message.text() !== message) {
          $message.text(message);
        }
        $status.find('.orbit-live-login').prop('hidden', !login);
        showAge();
      }

      function unavailable(status) {
        var message = 'Unable to update; retrying automatically';
        if (status === 401) {
          message = 'Your session has expired. Sign in again to resume automatic updates.';
        } else if (status === 403) {
          message = 'Access denied';
        } else if (status === 404) {
          message = 'This orb is no longer available';
        }
        showStatus(message, true, status === 401);
      }

      // Highlight rows that appeared or changed status since the last
      // snapshot: the sign that orbit moved an orb along.
      function highlight($table, before) {
        var $changed = $table.find('tbody tr[data-object-id]').filter(function () {
          return before[this.getAttribute('data-object-id')] !== this.getAttribute('data-orbit-status');
        });
        $changed.addClass('orbit-changed');
        window.requestAnimationFrame(function () {
          window.requestAnimationFrame(function () {
            $changed.removeClass('orbit-changed');
          });
        });
      }

      function update(html) {
        var $next = $('<div>').append($.parseHTML(html));
        var $table = $content.find('table.datatable');
        if ($table.length) {
          var $overview = $next.find('.orbit-overview');
          var overview = $overview.prop('outerHTML');
          if (overview !== lastOverview) {
            $content.find('.orbit-overview').remove();
            $content.prepend($overview);
            lastOverview = overview;
          }
          var $nextTable = $next.find('table.datatable');
          var markup = $nextTable.find('tbody').html() + $nextTable.find('tfoot').html();
          if (markup !== lastMarkup) {
            var before = statuses($table);
            $table.find('tbody').replaceWith($nextTable.find('tbody'));
            $table.find('tfoot').remove();
            $table.append($nextTable.find('tfoot'));
            if ($table[0].config) {
              $table.trigger('update');
            } else {
              horizon.datatables.set_table_sorting($content);
            }
            horizon.datatables.qs[$table.attr('id')].cache();
            highlight($table, before);
            lastMarkup = markup;
          }
        } else if (html !== lastMarkup) {
          $content.empty().append($next.contents());
          lastMarkup = html;
        }
        lastUpdate = Date.now();
        showStatus('Live · updates every 5 seconds', false, false);
        // One ping per snapshot received: restart the animation.
        var dot = $status.find('.orbit-live-dot')[0];
        dot.classList.remove('orbit-tick');
        void dot.offsetWidth;
        dot.classList.add('orbit-tick');
      }

      function schedule() {
        if (!stopped && !document.hidden) {
          timer = window.setTimeout(refresh, 5000);
        }
      }

      function refresh() {
        window.clearTimeout(timer);
        if (stopped || document.hidden || request) {
          return;
        }
        request = $.ajax({
          url: $root.attr('data-url'),
          data: {live: '1'},
          dataType: 'json',
          cache: false,
          global: false,
          timeout: 35000
        }).done(function (data) {
          if (pendingRefresh) {
            return;
          }
          try {
            if (data && typeof data.html === 'string') {
              update(data.html);
            } else {
              unavailable();
            }
          } catch (error) {
            unavailable();
          }
        }).fail(function (xhr) {
          if (!stopped) {
            unavailable(xhr.status);
          }
        }).always(function () {
          request = null;
          if (pendingRefresh) {
            pendingRefresh = false;
            refresh();
          } else {
            schedule();
          }
        });
      }

      function startTicker() {
        window.clearInterval(ticker);
        showAge();
        ticker = window.setInterval(showAge, 1000);
      }

      lastOverview = $content.find('.orbit-overview').prop('outerHTML');
      // Horizon's filter adds its "no results" row in the user's language;
      // the panel is English only. Live snapshots replace the whole tbody,
      // so the server's own empty message is never rewritten.
      new window.MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
          $(mutation.addedNodes).filter('tr.empty').children('td')
            .text('No items to display.');
        });
      }).observe($content[0], {childList: true, subtree: true});
      document.addEventListener('visibilitychange', function () {
        window.clearTimeout(timer);
        if (!document.hidden) {
          if (request) {
            pendingRefresh = true;
          } else {
            refresh();
          }
        }
      });
      window.addEventListener('pagehide', function () {
        stopped = true;
        window.clearTimeout(timer);
        window.clearInterval(ticker);
        if (request) {
          request.abort();
        }
      });
      window.addEventListener('pageshow', function (event) {
        if (event.persisted) {
          stopped = false;
          startTicker();
          refresh();
        }
      });
      startTicker();
      schedule();
    });
  });
}(jQuery));
