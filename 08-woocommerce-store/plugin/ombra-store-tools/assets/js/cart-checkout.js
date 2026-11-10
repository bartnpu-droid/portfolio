/**
 * Free shipping bar inside the Cart and Checkout blocks.
 *
 * Uses the ExperimentalOrderMeta slot, which receives the live cart from the Store API.
 * The numbers and the message come from the server (cart.extensions['ombra-store-tools']),
 * so the bar, the mini-cart and the announcement bar always say the same thing.
 * Plain JavaScript with WordPress globals: no build step.
 */
( function ( wp, wc ) {
	if ( ! wp || ! wp.plugins || ! wc || ! wc.blocksCheckout ) {
		return;
	}

	var el = wp.element.createElement;
	var ExperimentalOrderMeta = wc.blocksCheckout.ExperimentalOrderMeta;

	function FreeShippingBar( props ) {
		var data = props.extensions && props.extensions[ 'ombra-store-tools' ];
		if ( ! data || ! data.enabled || data.is_empty ) {
			return null;
		}
		var percent = Math.round( Math.min( 1, Math.max( 0, data.progress ) ) * 100 );

		return el(
			'div',
			{
				className: 'ombra-fsb ombra-fsb--bar ombra-fsb--blocks' + ( data.unlocked ? ' is-unlocked' : '' ),
				style: { '--ombra-fsb-color': data.color },
			},
			el( 'p', { className: 'ombra-fsb__message', 'aria-live': 'polite' }, data.message ),
			el(
				'div',
				{
					className: 'ombra-fsb__track',
					role: 'progressbar',
					'aria-label': data.message,
					'aria-valuemin': 0,
					'aria-valuemax': 100,
					'aria-valuenow': percent,
				},
				el( 'span', { className: 'ombra-fsb__fill', style: { width: percent + '%' } } )
			)
		);
	}

	wp.plugins.registerPlugin( 'ombra-free-shipping-bar', {
		scope: 'woocommerce-checkout',
		render: function () {
			return el( ExperimentalOrderMeta, null, el( FreeShippingBar ) );
		},
	} );
} )( window.wp, window.wc );
