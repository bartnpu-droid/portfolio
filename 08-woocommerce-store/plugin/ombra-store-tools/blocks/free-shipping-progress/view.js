/**
 * Keeps every "Free shipping progress" block on the page in step with the cart.
 *
 * WooCommerce announces cart changes with DOM events (product buttons, the Interactivity API
 * mini-cart, the Cart block, classic jQuery add-to-cart). On any of them we read the cart once
 * from the public Store API and repaint from cart.extensions['ombra-store-tools'], which the
 * plugin fills on the server. No private WooCommerce stores are used.
 */
const SELECTOR = '[data-ombra-fsb]';
let timer = 0;
let controller = null;

function paint( block, data ) {
	block.hidden = ! data.enabled;
	block.classList.toggle( 'is-unlocked', !! data.unlocked );
	block.classList.toggle( 'is-empty', !! data.is_empty );
	block.style.setProperty( '--ombra-fsb-color', data.color );

	const message = block.querySelector( '.ombra-fsb__message' );
	if ( message && message.textContent !== data.message ) {
		message.textContent = data.message;
	}

	const track = block.querySelector( '.ombra-fsb__track' );
	if ( track ) {
		const percent = Math.round( Math.min( 1, Math.max( 0, data.progress ) ) * 100 );
		track.setAttribute( 'aria-valuenow', String( percent ) );
		track.setAttribute( 'aria-label', data.message );
		track.querySelector( '.ombra-fsb__fill' ).style.width = percent + '%';
	}
}

async function refresh() {
	const blocks = document.querySelectorAll( SELECTOR );
	if ( ! blocks.length ) {
		return;
	}
	if ( controller ) {
		controller.abort();
	}
	controller = new AbortController();
	try {
		const response = await fetch( blocks[ 0 ].dataset.ombraFsbCart, {
			credentials: 'same-origin',
			headers: { Accept: 'application/json' },
			signal: controller.signal,
		} );
		if ( ! response.ok ) {
			return;
		}
		const cart = await response.json();
		const data = cart && cart.extensions && cart.extensions[ 'ombra-store-tools' ];
		if ( data ) {
			blocks.forEach( ( block ) => paint( block, data ) );
		}
	} catch ( error ) {
		if ( error.name !== 'AbortError' ) {
			// Keep the last known state; the next cart event will try again.
		}
	}
}

function schedule() {
	window.clearTimeout( timer );
	timer = window.setTimeout( refresh, 150 );
}

[ 'wc-blocks_added_to_cart', 'wc-blocks_removed_from_cart' ].forEach( ( name ) =>
	document.addEventListener( name, schedule )
);
window.addEventListener( 'wc-blocks_store_sync_required', schedule );
window.addEventListener( 'pageshow', ( event ) => event.persisted && schedule() );

// Classic WooCommerce pages announce cart changes through jQuery.
if ( window.jQuery ) {
	window.jQuery( document.body ).on( 'added_to_cart removed_from_cart updated_cart_totals wc_fragments_refreshed', schedule );
}
