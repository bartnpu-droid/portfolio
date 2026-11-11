<?php
/**
 * Fills a fresh WordPress + WooCommerce site with the Ombra demo store.
 *
 * Used twice:
 * - locally:            wp eval-file setup.php
 * - in WordPress Playground: the blueprint writes this file and runs it after installing everything.
 *
 * Product photos are read from OMBRA_IMAGES (a folder with the JPEG renders).
 * Running it again does not create duplicates.
 *
 * @package Ombra
 */

defined( 'ABSPATH' ) || exit;

if ( ! defined( 'OMBRA_IMAGES' ) ) {
	define( 'OMBRA_IMAGES', WP_CONTENT_DIR . '/ombra-setup/images' );
}

require_once ABSPATH . 'wp-admin/includes/image.php';
require_once ABSPATH . 'wp-admin/includes/file.php';
require_once ABSPATH . 'wp-admin/includes/media.php';

/**
 * Log a line (WP-CLI or Playground output).
 *
 * @param string $message Text.
 */
function ombra_setup_log( $message ) {
	if ( defined( 'WP_CLI' ) && WP_CLI ) {
		WP_CLI::log( $message );
	} else {
		echo esc_html( $message ) . "\n";
	}
}

/* ---------------------------------------------------------------- site and store settings */

update_option( 'blogname', 'Ombra' );
update_option( 'blogdescription', 'Candles and home fragrance, poured by hand' );
update_option( 'permalink_structure', '/%postname%/' );
update_option( 'timezone_string', 'America/New_York' );

$ombra_options = array(
	'woocommerce_store_address'                    => '12 Orchard Street',
	'woocommerce_store_city'                       => 'Hudson',
	'woocommerce_default_country'                  => 'US:NY',
	'woocommerce_store_postcode'                   => '12534',
	'woocommerce_currency'                         => 'USD',
	'woocommerce_price_num_decimals'               => '2',
	'woocommerce_weight_unit'                      => 'g',
	'woocommerce_calc_taxes'                       => 'no',
	'woocommerce_enable_reviews'                   => 'no',
	'woocommerce_coming_soon'                      => 'no',
	'woocommerce_store_pages_only'                 => 'no',
	'woocommerce_enable_guest_checkout'            => 'yes',
	'woocommerce_enable_checkout_login_reminder'   => 'no',
	'woocommerce_enable_signup_and_login_from_checkout' => 'no',
	'woocommerce_allow_tracking'                   => 'no',
	'woocommerce_show_marketplace_suggestions'     => 'no',
	'woocommerce_task_list_hidden'                 => 'yes',
	'woocommerce_task_list_complete'               => 'yes',
	'woocommerce_onboarding_profile'               => array( 'skipped' => true ),
	'woocommerce_shop_page_display'                => '',
	'woocommerce_catalog_columns'                  => 3,
	'woocommerce_thumbnail_cropping'               => '1:1',
	'woocommerce_ship_to_countries'                => '',
	'woocommerce_ship_to_destination'              => 'shipping',
);
foreach ( $ombra_options as $ombra_key => $ombra_value ) {
	update_option( $ombra_key, $ombra_value );
}

/* Demo payment: the order is created, nothing is charged. */
update_option(
	'woocommerce_cheque_settings',
	array(
		'enabled'      => 'yes',
		'title'        => 'Demo payment (nothing is charged)',
		'description'  => 'This is a portfolio demo. Your order is created so you can see the confirmation, but no payment is taken and nothing ships.',
		'instructions' => 'Demo order: nothing was charged and nothing will ship.',
	)
);

/* Shipping: flat rate everywhere, free over $75. */
$ombra_zone = new WC_Shipping_Zone( 0 );
$ombra_have = wp_list_pluck( $ombra_zone->get_shipping_methods(), 'id' );
if ( ! in_array( 'flat_rate', $ombra_have, true ) ) {
	$ombra_instance = $ombra_zone->add_shipping_method( 'flat_rate' );
	update_option(
		'woocommerce_flat_rate_' . $ombra_instance . '_settings',
		array(
			'title'      => 'Standard shipping',
			'tax_status' => 'none',
			'cost'       => '6.50',
		)
	);
}
if ( ! in_array( 'free_shipping', $ombra_have, true ) ) {
	$ombra_instance = $ombra_zone->add_shipping_method( 'free_shipping' );
	update_option(
		'woocommerce_free_shipping_' . $ombra_instance . '_settings',
		array(
			'title'            => 'Free shipping',
			'requires'         => 'min_amount',
			'min_amount'       => '75',
			'ignore_discounts' => 'no',
		)
	);
}
WC_Cache_Helper::get_transient_version( 'shipping', true );

/* ---------------------------------------------------------------- images */

/**
 * Import a render into the media library once, return the attachment ID.
 *
 * @param string $file File name in OMBRA_IMAGES.
 * @param string $alt  Alt text.
 * @return int
 */
function ombra_setup_image( $file, $alt ) {
	$existing = get_posts(
		array(
			'post_type'   => 'attachment',
			'post_status' => 'inherit',
			'meta_key'    => '_ombra_source', // phpcs:ignore WordPress.DB.SlowDBQuery.slow_db_query_meta_key
			'meta_value'  => $file, // phpcs:ignore WordPress.DB.SlowDBQuery.slow_db_query_meta_value
			'fields'      => 'ids',
		)
	);
	$path = trailingslashit( OMBRA_IMAGES ) . $file;
	$hash = file_exists( $path ) ? md5_file( $path ) : '';
	if ( $existing ) {
		// Same photo as last time: keep it. A new render of the same file replaces the old one.
		if ( ! $hash || get_post_meta( $existing[0], '_ombra_hash', true ) === $hash ) {
			update_post_meta( $existing[0], '_wp_attachment_image_alt', $alt );
			return (int) $existing[0];
		}
		wp_delete_attachment( $existing[0], true );
	}
	if ( ! $hash ) {
		ombra_setup_log( "Missing image: $file" );
		return 0;
	}
	$tmp = wp_tempnam( $file );
	copy( $path, $tmp );
	$id = media_handle_sideload(
		array(
			'name'     => $file,
			'tmp_name' => $tmp,
		),
		0,
		$alt
	);
	if ( is_wp_error( $id ) ) {
		ombra_setup_log( 'Image error: ' . $id->get_error_message() );
		return 0;
	}
	update_post_meta( $id, '_ombra_source', $file );
	update_post_meta( $id, '_ombra_hash', $hash );
	update_post_meta( $id, '_wp_attachment_image_alt', $alt );
	return (int) $id;
}

// Only the sizes the store uses, so the import stays quick in Playground.
add_filter(
	'intermediate_image_sizes_advanced',
	static function ( $sizes ) {
		return array_intersect_key( $sizes, array_flip( array( 'thumbnail', 'medium', 'woocommerce_thumbnail', 'woocommerce_single', 'woocommerce_gallery_thumbnail' ) ) );
	}
);

/* ---------------------------------------------------------------- categories and attributes */

$ombra_categories = array(
	'candles'          => array( 'Candles', 'Coconut-soy candles in amber glass, brushed tins and hand-thrown terracotta. Each scent comes in two sizes.' ),
	'diffusers-sprays' => array( 'Diffusers + sprays', 'Our three scents without a flame: rattan reed diffusers for a steady background and room sprays for a quick change of mood.' ),
	'accessories'      => array( 'Accessories', 'The small things that make a candle burn better and look right on the table.' ),
	'gift-sets'        => array( 'Gift sets', 'Boxed, wrapped and ready to give, with a handwritten card if you like.' ),
);
$ombra_cat_ids    = array();
$ombra_order      = 0;
foreach ( $ombra_categories as $ombra_slug => $ombra_cat ) {
	$ombra_term = get_term_by( 'slug', $ombra_slug, 'product_cat' );
	if ( ! $ombra_term ) {
		$ombra_term = wp_insert_term( $ombra_cat[0], 'product_cat', array( 'slug' => $ombra_slug, 'description' => $ombra_cat[1] ) );
		$ombra_term = get_term( $ombra_term['term_id'], 'product_cat' );
	}
	update_term_meta( $ombra_term->term_id, 'order', $ombra_order++ );
	$ombra_cat_ids[ $ombra_slug ] = (int) $ombra_term->term_id;
}
// Products without a category would land in "Uncategorized"; keep that one out of the way.
$ombra_uncat = get_term_by( 'slug', 'uncategorized', 'product_cat' );
if ( $ombra_uncat ) {
	update_term_meta( $ombra_uncat->term_id, 'order', 99 );
}

/**
 * Create a global attribute with its terms (once).
 *
 * @param string   $name  Attribute name.
 * @param string   $slug  Attribute slug, without "pa_".
 * @param string[] $terms Term names.
 * @return array{id: int, taxonomy: string, terms: array<string, int>}
 */
function ombra_setup_attribute( $name, $slug, $terms ) {
	$id = wc_attribute_taxonomy_id_by_name( $slug );
	if ( ! $id ) {
		$id = wc_create_attribute(
			array(
				'name'         => $name,
				'slug'         => $slug,
				'type'         => 'select',
				'order_by'     => 'menu_order',
				'has_archives' => false,
			)
		);
	}
	$taxonomy = wc_attribute_taxonomy_name( $slug );
	if ( ! taxonomy_exists( $taxonomy ) ) {
		register_taxonomy( $taxonomy, array( 'product' ), array( 'hierarchical' => false ) );
	}
	$ids = array();
	foreach ( $terms as $i => $term_name ) {
		$term = get_term_by( 'name', $term_name, $taxonomy );
		if ( ! $term ) {
			$new  = wp_insert_term( $term_name, $taxonomy );
			$term = get_term( $new['term_id'], $taxonomy );
		}
		update_term_meta( $term->term_id, 'order', $i );
		$ids[ $term_name ] = (int) $term->term_id;
	}
	return array(
		'id'       => (int) $id,
		'taxonomy' => $taxonomy,
		'terms'    => $ids,
	);
}

$ombra_size  = ombra_setup_attribute( 'Size', 'size', array( '200 g', '400 g' ) );
$ombra_scent = ombra_setup_attribute( 'Scent', 'scent', array( 'Fig & Cedar', 'Sea Salt & Sage', 'Amber & Smoke' ) );

/* ---------------------------------------------------------------- products */

$ombra_scents = array(
	'fig'   => array(
		'name'  => 'Fig & Cedar',
		'top'   => 'Green fig leaf, bergamot',
		'heart' => 'Fig milk, violet leaf',
		'base'  => 'Cedarwood, vetiver',
		'story' => 'Green and woody, like a garden wall still warm after a summer day. The fig leaf is bright and a little bitter, the cedar keeps it grounded.',
		'slug'  => 'fig-cedar-candle',
		'term'  => 'Fig & Cedar',
		'glass' => 'amber glass',
	),
	'salt'  => array(
		'name'  => 'Sea Salt & Sage',
		'top'   => 'Sea salt, grapefruit',
		'heart' => 'Wild sage, ambrette',
		'base'  => 'Driftwood, white musk',
		'story' => 'Fresh and airy: windows open, linen drying, the coast close by. A clean scent for kitchens and bathrooms that never turns soapy.',
		'slug'  => 'sea-salt-sage-candle',
		'term'  => 'Sea Salt & Sage',
		'glass' => 'sage-green glass',
	),
	'amber' => array(
		'name'  => 'Amber & Smoke',
		'top'   => 'Pink pepper, smoked birch',
		'heart' => 'Amber resin, labdanum',
		'base'  => 'Tonka bean, vanilla',
		'story' => 'Warm and deep, a fire burning low on a cold night. Smoky at first light, then soft and resinous once the wax pool forms.',
		'slug'  => 'amber-smoke-candle',
		'term'  => 'Amber & Smoke',
		'glass' => 'smoked glass',
	),
);

/**
 * Find a product by slug.
 *
 * @param string $slug Slug.
 * @return WC_Product|null
 */
function ombra_setup_find( $slug ) {
	$post = get_page_by_path( $slug, OBJECT, 'product' );
	return $post ? wc_get_product( $post->ID ) : null;
}

/**
 * Shared fields for every product.
 *
 * @param WC_Product $product Product.
 * @param array      $data    Data.
 */
function ombra_setup_fill( $product, $data ) {
	$product->set_name( $data['name'] );
	$product->set_slug( $data['slug'] );
	$product->set_status( 'publish' );
	$product->set_catalog_visibility( 'visible' );
	$product->set_short_description( $data['short'] );
	$product->set_description( $data['description'] );
	$product->set_category_ids( array( $data['category'] ) );
	$product->set_featured( ! empty( $data['featured'] ) );
	$product->set_menu_order( $data['order'] );
	$product->set_reviews_allowed( false );
	$product->set_image_id( $data['images'][0] );
	$product->set_gallery_image_ids( array_slice( $data['images'], 1 ) );
	$product->update_meta_data( '_ombra_badge', $data['badge'] ?? '' );
	foreach ( array( 'top', 'heart', 'base' ) as $note ) {
		$product->update_meta_data( '_ombra_notes_' . $note, $data['notes'][ $note ] ?? '' );
	}
	$product->update_meta_data( '_ombra_burn_time', $data['burn'] ?? '' );
	$product->update_meta_data( '_ombra_wax', $data['wax'] ?? '' );
}

/**
 * Create or update a simple product.
 *
 * @param array $data Data.
 * @return int
 */
function ombra_setup_simple( $data ) {
	$product = ombra_setup_find( $data['slug'] );
	if ( ! $product || ! $product->is_type( 'simple' ) ) {
		$product = new WC_Product_Simple();
	}
	ombra_setup_fill( $product, $data );
	$product->set_regular_price( $data['price'] );
	$product->set_sale_price( $data['sale'] ?? '' );
	$product->set_weight( $data['weight'] ?? '' );
	return $product->save();
}

/**
 * Create or update a variable product with one attribute.
 *
 * @param array $data      Data.
 * @param array $attribute Attribute (from ombra_setup_attribute()).
 * @param array $options   Term name => array( price, sale, image, weight ).
 * @return int
 */
function ombra_setup_variable( $data, $attribute, $options ) {
	$product = ombra_setup_find( $data['slug'] );
	if ( ! $product || ! $product->is_type( 'variable' ) ) {
		$product = new WC_Product_Variable();
	}
	ombra_setup_fill( $product, $data );

	$attr = new WC_Product_Attribute();
	$attr->set_id( $attribute['id'] );
	$attr->set_name( $attribute['taxonomy'] );
	$attr->set_options( array_map( static fn( $name ) => $attribute['terms'][ $name ], array_keys( $options ) ) );
	$attr->set_visible( true );
	$attr->set_variation( true );
	$product->set_attributes( array( $attr ) );
	$first = get_term( $attribute['terms'][ array_key_first( $options ) ], $attribute['taxonomy'] );
	$product->set_default_attributes( array( $attribute['taxonomy'] => $first->slug ) );
	$product_id = $product->save();

	$existing = array();
	foreach ( $product->get_children() as $child_id ) {
		$child = wc_get_product( $child_id );
		if ( $child ) {
			$existing[ $child->get_attributes()[ $attribute['taxonomy'] ] ?? '' ] = $child;
		}
	}
	$i = 0;
	foreach ( $options as $term_name => $option ) {
		$term      = get_term( $attribute['terms'][ $term_name ], $attribute['taxonomy'] );
		$variation = $existing[ $term->slug ] ?? new WC_Product_Variation();
		$variation->set_parent_id( $product_id );
		$variation->set_attributes( array( $attribute['taxonomy'] => $term->slug ) );
		$variation->set_regular_price( $option['price'] );
		$variation->set_sale_price( $option['sale'] ?? '' );
		$variation->set_image_id( $option['image'] );
		$variation->set_weight( $option['weight'] ?? '' );
		$variation->set_menu_order( $i++ );
		$variation->set_status( 'publish' );
		$variation->set_stock_status( 'instock' );
		$variation->save();
	}
	WC_Product_Variable::sync( $product_id );
	return $product_id;
}

$ombra_wax  = 'Coconut-soy wax, cotton wick';
$ombra_menu = 0;
$ombra_made = array();

foreach ( $ombra_scents as $ombra_key => $ombra_s ) {
	$ombra_main  = ombra_setup_image( "jar-$ombra_key-200.jpg", "{$ombra_s['name']} candle in a {$ombra_s['glass']} jar, 200 g" );
	$ombra_large = ombra_setup_image( "jar-$ombra_key-400.jpg", "{$ombra_s['name']} candle, 400 g" );
	$ombra_lit   = ombra_setup_image( "jar-$ombra_key-200-lit.jpg", "{$ombra_s['name']} candle burning in a dark room" );

	$ombra_made[ $ombra_key ] = ombra_setup_variable(
		array(
			'name'        => $ombra_s['name'],
			'slug'        => $ombra_s['slug'],
			'short'       => $ombra_s['story'],
			'description' => '<p>Poured by hand in batches of 60 and cured for two weeks, so the scent fills the room from the first burn. Each jar has an ash wood lid that keeps dust out and the scent in.</p><p>The ' . $ombra_s['glass'] . ' is thick and made to be kept: soak it in warm water and the last of the wax lifts out.</p>',
			'category'    => $ombra_cat_ids['candles'],
			'featured'    => 'salt' !== $ombra_key,
			'order'       => $ombra_menu++,
			'badge'       => array(
				'fig'   => 'bestseller',
				'salt'  => '',
				'amber' => 'new',
			)[ $ombra_key ],
			'images'      => array( $ombra_main, $ombra_lit, $ombra_large ),
			'notes'       => $ombra_s,
			'burn'        => '45 hours (200 g), 80 hours (400 g)',
			'wax'         => $ombra_wax,
		),
		$ombra_size,
		array(
			'200 g' => array(
				'price'  => '34',
				'image'  => $ombra_main,
				'weight' => '420',
			),
			'400 g' => array(
				'price'  => '52',
				'image'  => $ombra_large,
				'weight' => '760',
			),
		)
	);
	ombra_setup_log( "Product: {$ombra_s['name']}" );
}

$ombra_made['ember'] = ombra_setup_simple(
	array(
		'name'        => 'Ember Terracotta Candle',
		'slug'        => 'ember-terracotta-candle',
		'short'       => 'Our evening scent in a hand-thrown terracotta bowl: smoked orange peel, clove and amber. Every bowl is a little different.',
		'description' => '<p>Thrown on a wheel by a small pottery upstate, then filled with 300 g of coconut-soy wax and three cotton wicks for a wide, even pool. When the candle is done, the bowl makes a good home for a small plant.</p>',
		'category'    => $ombra_cat_ids['candles'],
		'order'       => $ombra_menu++,
		'badge'       => 'limited',
		'images'      => array( ombra_setup_image( 'vessel.jpg', 'Ember candle in a terracotta bowl' ), ombra_setup_image( 'vessel-lit.jpg', 'Ember terracotta candle, lit' ) ),
		'notes'       => array(
			'top'   => 'Smoked orange peel',
			'heart' => 'Clove, black tea',
			'base'  => 'Amber, cedar',
		),
		'burn'        => 'About 60 hours',
		'wax'         => 'Coconut-soy wax, three cotton wicks',
		'price'       => '58',
		'weight'      => '900',
	)
);

$ombra_tins = array();
foreach ( $ombra_scents as $ombra_key => $ombra_s ) {
	$ombra_tins[ $ombra_s['term'] ] = array(
		'price'  => '18',
		'image'  => ombra_setup_image( "tin-$ombra_key.jpg", "{$ombra_s['name']} travel candle in a brushed tin" ),
		'weight' => '120',
	);
}
$ombra_made['tin'] = ombra_setup_variable(
	array(
		'name'        => 'Travel Candle',
		'slug'        => 'travel-candle',
		'short'       => 'Any of our three scents in a brushed aluminium tin with a lid. Small enough for a weekend bag, big enough for a week of evenings.',
		'description' => '<p>80 g of coconut-soy wax in a tin you can close after every burn, so the scent stays fresh. Choose the scent above: the label on the lid changes with it.</p>',
		'category'    => $ombra_cat_ids['candles'],
		'order'       => $ombra_menu++,
		'images'      => array_column( $ombra_tins, 'image' ),
		'burn'        => 'About 20 hours',
		'wax'         => $ombra_wax,
	),
	$ombra_scent,
	$ombra_tins
);

$ombra_diffusers = array();
foreach ( $ombra_scents as $ombra_key => $ombra_s ) {
	$ombra_diffusers[ $ombra_s['term'] ] = array(
		'price'  => '46',
		'image'  => ombra_setup_image( "diffuser-$ombra_key.jpg", "{$ombra_s['name']} reed diffuser with rattan reeds" ),
		'weight' => '380',
	);
}
$ombra_made['diffuser'] = ombra_setup_variable(
	array(
		'name'        => 'Reed Diffuser',
		'slug'        => 'reed-diffuser',
		'short'       => 'A steady, quiet background scent for a hallway or a bathroom, with eight rattan reeds. Lasts about three months.',
		'description' => '<p>100 ml of plant-based diffuser oil in a heavy glass bottle with a walnut collar. Turn the reeds once a week for a stronger scent.</p>',
		'category'    => $ombra_cat_ids['diffusers-sprays'],
		'featured'    => true,
		'order'       => $ombra_menu++,
		'images'      => array_column( $ombra_diffusers, 'image' ),
		'wax'         => 'Plant-based diffuser oil, 8 rattan reeds',
	),
	$ombra_scent,
	$ombra_diffusers
);

$ombra_sprays = array();
foreach ( $ombra_scents as $ombra_key => $ombra_s ) {
	$ombra_sprays[ $ombra_s['term'] ] = array(
		'price'  => '28',
		'sale'   => '24',
		'image'  => ombra_setup_image( "spray-$ombra_key.jpg", "{$ombra_s['name']} room spray in a glass bottle" ),
		'weight' => '260',
	);
}
$ombra_made['spray'] = ombra_setup_variable(
	array(
		'name'        => 'Room Spray',
		'slug'        => 'room-spray',
		'short'       => 'Two sprays to change the mood of a room in a second. Also lovely on linen and curtains.',
		'description' => '<p>100 ml in a glass bottle with a brass pump. A water and plant-alcohol base that dries in seconds and leaves no marks on fabric.</p>',
		'category'    => $ombra_cat_ids['diffusers-sprays'],
		'order'       => $ombra_menu++,
		'images'      => array_column( $ombra_sprays, 'image' ),
		'wax'         => 'Water and plant-alcohol base',
	),
	$ombra_scent,
	$ombra_sprays
);

$ombra_made['matches'] = ombra_setup_simple(
	array(
		'name'        => 'Long Matches',
		'slug'        => 'long-matches',
		'short'       => '34 long matches in a glass jar with a cork lid and a striker on the side. Long enough to reach the wick of a half-burned candle.',
		'description' => '<p>11 cm matches with dark heads. When the jar is empty, refill it, or keep it for cotton buds in the bathroom.</p>',
		'category'    => $ombra_cat_ids['accessories'],
		'order'       => $ombra_menu++,
		'images'      => array( ombra_setup_image( 'matches.jpg', 'Long matches in a glass jar with a cork lid' ) ),
		'wax'         => '34 matches, striker on the jar',
		'price'       => '14',
		'weight'      => '300',
	)
);

$ombra_made['set'] = ombra_setup_simple(
	array(
		'name'        => 'The Evening Set',
		'slug'        => 'the-evening-set',
		'short'       => 'Fig & Cedar candle (200 g), Fig & Cedar room spray and a jar of long matches in a charcoal gift box.',
		'description' => '<p>Everything for a slow evening, boxed and ready to give. Tick "This order is a gift" at checkout and we will leave out the receipt and add a handwritten card with your note.</p>',
		'category'    => $ombra_cat_ids['gift-sets'],
		'featured'    => true,
		'order'       => $ombra_menu++,
		'images'      => array( ombra_setup_image( 'giftset.jpg', 'The Evening Set: candle, room spray and matches with a charcoal gift box' ) ),
		'notes'       => array(
			'top'   => 'Green fig leaf, bergamot',
			'heart' => 'Fig milk, violet leaf',
			'base'  => 'Cedarwood, vetiver',
		),
		'price'       => '82',
		'weight'      => '1200',
	)
);
ombra_setup_log( 'Products ready: ' . count( $ombra_made ) );

/* ---------------------------------------------------------------- pages */

/**
 * Create or update a page.
 *
 * @param string $slug    Slug.
 * @param string $title   Title.
 * @param string $content Block markup.
 * @return int
 */
function ombra_setup_page( $slug, $title, $content ) {
	$page = get_page_by_path( $slug );
	$args = array(
		'post_type'    => 'page',
		'post_status'  => 'publish',
		'post_name'    => $slug,
		'post_title'   => $title,
		'post_content' => $content,
	);
	if ( $page ) {
		$args['ID'] = $page->ID;
		return wp_update_post( $args );
	}
	return wp_insert_post( $args );
}

/**
 * Paragraph block.
 *
 * @param string $text Text.
 * @return string
 */
function ombra_setup_p( $text ) {
	return "<!-- wp:paragraph -->\n<p>$text</p>\n<!-- /wp:paragraph -->\n\n";
}

/**
 * Heading block.
 *
 * @param string $text Text.
 * @return string
 */
function ombra_setup_h( $text ) {
	return "<!-- wp:heading -->\n<h2 class=\"wp-block-heading\">$text</h2>\n<!-- /wp:heading -->\n\n";
}

/**
 * Question and answer as a details block.
 *
 * @param string $question Question.
 * @param string $answer   Answer.
 * @return string
 */
function ombra_setup_qa( $question, $answer ) {
	return "<!-- wp:details -->\n<details class=\"wp-block-details\"><summary>$question</summary><!-- wp:paragraph -->\n<p>$answer</p>\n<!-- /wp:paragraph --></details>\n<!-- /wp:details -->\n\n";
}

ombra_setup_page(
	'our-story',
	'Our story',
	ombra_setup_p( '<em>Ombra</em> means shadow in Italian. We liked the idea that a good candle is as much about the shadows it makes as about the light.' )
	. ombra_setup_p( 'Ombra is a small, made-up brand created for this WooCommerce demo. The products, the photos (rendered in Blender) and the words are all part of the demo, but the store works like a real one: you can browse, choose a size and a scent, add to the bag and check out.' )
	. ombra_setup_h( 'How the candles are made' )
	. ombra_setup_p( 'Coconut-soy wax, cotton wicks and fragrance oils free from phthalates. Each batch of 60 is poured by hand and left to cure for two weeks before it ships.' )
	. ombra_setup_h( 'Vessels worth keeping' )
	. ombra_setup_p( 'Amber glass, brushed aluminium and terracotta. When the wax is gone, soak the vessel in warm water and the last of it lifts out. They make good homes for pens, matches and small plants.' )
);

ombra_setup_page(
	'candle-care',
	'Candle care',
	ombra_setup_p( 'A few habits make a candle burn cleaner, longer and with a fuller scent.' )
	. ombra_setup_h( 'The first burn' )
	. ombra_setup_p( 'Let it burn for about two hours the first time, until the melted wax reaches the edge of the jar. Wax has a memory: a short first burn leaves a tunnel down the middle.' )
	. ombra_setup_h( 'Before every burn' )
	. ombra_setup_p( 'Trim the wick to about 5 mm. A short wick gives a calm flame, no soot on the glass and a longer life.' )
	. ombra_setup_h( 'How long to burn' )
	. ombra_setup_p( 'Up to four hours at a time. Put the flame out with the lid or a snuffer, never with water, and keep it away from drafts, children and pets.' )
	. ombra_setup_h( 'When to stop' )
	. ombra_setup_p( 'Stop when about 1 cm of wax is left at the bottom. The glass can get too hot after that.' )
);

ombra_setup_page(
	'shipping-returns',
	'Shipping + returns',
	ombra_setup_p( '<strong>This is a demo store.</strong> Orders placed here are not real: nothing is charged and nothing ships. The rules below are written as a real shop would write them.' )
	. ombra_setup_h( 'Shipping' )
	. ombra_setup_p( 'Orders ship in 1–2 working days. Standard shipping is $6.50, and free on orders over $75: the bar in your bag shows how close you are.' )
	. ombra_setup_h( 'Gifts' )
	. ombra_setup_p( 'Tick "This order is a gift" at checkout. We leave out the receipt and write your note on a card by hand.' )
	. ombra_setup_h( 'Returns' )
	. ombra_setup_p( 'Unused items can be returned within 30 days. Candles that have been lit cannot be returned, but if something is wrong with yours, write to us and we will make it right.' )
);

ombra_setup_page(
	'faq',
	'FAQ',
	ombra_setup_qa( 'Is this a real shop?', 'No. Ombra is a made-up brand for a WooCommerce portfolio demo. You can try everything, including checkout, but nothing is charged and nothing ships.' )
	. ombra_setup_qa( 'How long does a candle burn?', 'About 45 hours for the 200 g jar and 80 hours for the 400 g jar, if you trim the wick and burn up to four hours at a time.' )
	. ombra_setup_qa( 'What is the wax made of?', 'A blend of coconut and soy wax with cotton wicks. It burns cooler and cleaner than paraffin.' )
	. ombra_setup_qa( 'Can I reuse the jar?', 'Yes. Pour in warm water, wait an hour, and the last of the wax lifts out. Wash it with soap and it is ready for pens, plants or matches.' )
	. ombra_setup_qa( 'Do you ship abroad?', 'In this demo the checkout accepts any address, so you can try it with yours. A real shop would set its countries in WooCommerce → Settings → Shipping.' )
);

ombra_setup_page(
	'contact',
	'Contact',
	ombra_setup_p( 'Ombra is a demo store, so there is no one on the other end of this page.' )
	. ombra_setup_p( 'A real version would have a contact form, an email address and opening hours here.' )
);

/* Home page shows the theme's front page template; blog posts are not used. */
update_option( 'show_on_front', 'posts' );

/* ---------------------------------------------------------------- theme and plugin */

if ( wp_get_theme( 'ombra' )->exists() && 'ombra' !== get_stylesheet() ) {
	switch_theme( 'ombra' );
}
update_option( 'ombra_fsb_goal_source', 'method' );

/* Demo visitors are logged in as admin (so they can open the settings); keep the storefront clean. */
update_user_meta( 1, 'show_admin_bar_front', 'false' );
update_option( 'ombra_demo_mode', 1 );
delete_transient( '_wc_activation_redirect' );

flush_rewrite_rules();
wc_delete_product_transients();
WC_Cache_Helper::get_transient_version( 'product', true );
ombra_setup_log( 'Ombra demo store is ready.' );
