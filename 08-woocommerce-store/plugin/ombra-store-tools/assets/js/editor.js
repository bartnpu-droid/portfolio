/**
 * Editor side of the three Ombra blocks: a live server-side preview and a style switch.
 * Plain JavaScript with WordPress globals: no build step.
 */
( function ( wp ) {
	var el = wp.element.createElement;
	var __ = wp.i18n.__;
	var ServerSideRender = wp.serverSideRender;
	var InspectorControls = wp.blockEditor.InspectorControls;
	var useBlockProps = wp.blockEditor.useBlockProps;
	var PanelBody = wp.components.PanelBody;
	var SelectControl = wp.components.SelectControl;
	var Placeholder = wp.components.Placeholder;

	function makeEdit( options, empty ) {
		return function ( props ) {
			var blockProps = useBlockProps();
			var postId = props.context && props.context.postId;
			return el(
				'div',
				blockProps,
				el(
					InspectorControls,
					null,
					el(
						PanelBody,
						{ title: __( 'Style', 'ombra-store-tools' ) },
						el( SelectControl, {
							label: __( 'Show as', 'ombra-store-tools' ),
							value: props.attributes.variant,
							options: options,
							onChange: function ( value ) {
								props.setAttributes( { variant: value } );
							},
						} )
					)
				),
				el( ServerSideRender, {
					block: props.name,
					attributes: props.attributes,
					urlQueryArgs: postId ? { post_id: postId } : {},
					EmptyResponsePlaceholder: function () {
						return el( Placeholder, { label: empty, className: 'ombra-placeholder' } );
					},
				} )
			);
		};
	}

	wp.blocks.registerBlockType( 'ombra/free-shipping-progress', {
		edit: makeEdit(
			[
				{ label: __( 'Message and bar', 'ombra-store-tools' ), value: 'bar' },
				{ label: __( 'Message only', 'ombra-store-tools' ), value: 'text' },
			],
			__( 'Free shipping progress (turned off in WooCommerce → Settings → Ombra)', 'ombra-store-tools' )
		),
		save: function () {
			return null;
		},
	} );

	wp.blocks.registerBlockType( 'ombra/product-badge', {
		edit: makeEdit(
			[
				{ label: __( 'Over the image', 'ombra-store-tools' ), value: 'overlay' },
				{ label: __( 'Inline text', 'ombra-store-tools' ), value: 'inline' },
			],
			__( 'Product badge (shows when the product has one)', 'ombra-store-tools' )
		),
		save: function () {
			return null;
		},
	} );

	wp.blocks.registerBlockType( 'ombra/scent-notes', {
		edit: makeEdit(
			[
				{ label: __( 'Full list', 'ombra-store-tools' ), value: 'full' },
				{ label: __( 'One line', 'ombra-store-tools' ), value: 'line' },
			],
			__( 'Scent notes (filled in on the product)', 'ombra-store-tools' )
		),
		save: function () {
			return null;
		},
	} );
} )( window.wp );
